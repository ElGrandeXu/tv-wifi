"""Capture AVFoundation/VideoToolbox et orchestration de TV Wi-Fi sur Mac."""
import ctypes
import ipaddress
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

import dlna


def network_interfaces():
    try:
        result = subprocess.run(['/sbin/ifconfig', '-a'], capture_output=True,
                                text=True, timeout=4, check=True)
        addresses = re.findall(r'^\s+inet\s+(\d+\.\d+\.\d+\.\d+)\s', result.stdout, re.M)
        return list(dict.fromkeys(a for a in addresses if ipaddress.IPv4Address(a).is_private
                                  and not ipaddress.IPv4Address(a).is_loopback)) or ['0.0.0.0']
    except (OSError, ValueError, subprocess.SubprocessError):
        return ['0.0.0.0']


dlna.interfaces = network_interfaces


def find_ffmpeg():
    candidates = [shutil.which('ffmpeg'), '/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg',
                  '/usr/local/opt/ffmpeg@7/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg',
                  '/usr/local/bin/ffmpeg']
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise dlna.TVError('FFmpeg est absent. Lancez « Installer les prérequis.command » dans le dossier fourni.')


def parse_screens(output):
    screens = []
    in_video = False
    for line in output.splitlines():
        if 'AVFoundation video devices:' in line:
            in_video = True
        elif 'AVFoundation audio devices:' in line:
            in_video = False
        elif in_video:
            match = re.search(r'\[\d+\]\s+(Capture screen (\d+))\s*$', line)
            if match:
                name = match.group(1)
                screens.append((name, f'Écran {int(match.group(2)) + 1}'))
    return screens


def list_screens():
    result = subprocess.run([find_ffmpeg(), '-hide_banner', '-nostdin', '-f', 'avfoundation',
                             '-list_devices', 'true', '-i', ''],
                            capture_output=True, text=True, timeout=12)
    # FFmpeg quitte normalement avec un code non nul après une simple liste.
    screens = parse_screens(result.stderr + result.stdout)
    if not screens:
        raise dlna.TVError('Aucun écran détecté. Vérifiez l’autorisation d’enregistrement de l’écran '
                           'dans Réglages Système → Confidentialité et sécurité, puis relancez TV Wi-Fi.')
    return screens


def request_screen_permission():
    if sys.platform != 'darwin':
        raise dlna.TVError('Cette version fonctionne sur macOS uniquement.')
    quartz = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
    for name in ['CGPreflightScreenCaptureAccess', 'CGRequestScreenCaptureAccess']:
        getattr(quartz, name).restype = ctypes.c_bool
        getattr(quartz, name).argtypes = []
    if quartz.CGPreflightScreenCaptureAccess():
        return True
    return bool(quartz.CGRequestScreenCaptureAccess())


def capture_command(screen):
    if not re.fullmatch(r'Capture screen \d+', screen):
        raise dlna.TVError('Choisissez un écran ; aucune caméra ou entrée audio n’est utilisée.')
    return [find_ffmpeg(), '-hide_banner', '-loglevel', 'error', '-nostdin',
            '-f', 'avfoundation', '-framerate', '30', '-capture_cursor', '1',
            '-pixel_format', 'bgra', '-i', screen + ':none', '-an',
            '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease:force_divisible_by=2,'
                   'pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p',
            '-c:v', 'h264_videotoolbox', '-realtime', '1', '-b:v', '12M',
            '-maxrate', '12M', '-bufsize', '3M', '-g', '30', '-bf', '0',
            '-profile:v', 'baseline', '-pix_fmt', 'yuv420p',
            '-mpegts_flags', 'resend_headers', '-muxdelay', '0', '-muxpreload', '0',
            '-flush_packets', '1', '-f', 'mpegts', 'pipe:1']


class Controller:
    """Les événements sont consommés par Tk sur son thread principal."""
    def __init__(self):
        self.events = queue.Queue()
        self.state = 'idle'
        self.session = None
        self.cancel = threading.Event()
        self.worker = None
        self.lock = threading.RLock()

    def notify(self, state, message):
        self.state = state
        self.events.put(('state', state, message))

    def connect(self, ip, screen, known):
        if self.state != 'idle':
            return
        ip = dlna.parse_ip(ip)
        command = capture_command(screen)
        self.cancel = threading.Event()
        cancel = self.cancel
        self.notify('connecting', 'Connexion à ' + ip + '…')

        def work():
            session = None
            try:
                tv = dlna.resolve_tv(ip, known, cancel)
                session = dlna.CastSession(tv, cancel, command)
                session.start()
                with self.lock:
                    if cancel.is_set():
                        raise dlna.TVError('Connexion annulée.')
                    self.session = session
                    try:
                        dlna.save_preferences(tv)
                    except OSError:
                        pass
                    self.notify('connected', 'Connecté à ' + tv.name + ' — ' + tv.ip)
            except Exception as error:
                if session:
                    session.stop()
                self.session = None
                message = 'Déconnecté.' if cancel.is_set() else str(error)
                self.notify('idle', message)

        self.worker = threading.Thread(target=work, daemon=False)
        self.worker.start()

    def disconnect(self, reason=None):
        with self.lock:
            self.cancel.set()
            if self.state in {'connecting', 'disconnecting'}:
                self.notify('disconnecting', 'Annulation de la connexion…')
                return
            session = self.session
            if not session:
                return
            self.notify('disconnecting', 'Déconnexion…')

        def work():
            try:
                session.stop()
            finally:
                self.session = None
                self.notify('idle', reason or 'Déconnecté. Votre écran n’est plus partagé.')
        self.worker = threading.Thread(target=work, daemon=False)
        self.worker.start()

    def monitor(self):
        if self.state == 'connected' and self.session:
            if self.session.error or time.monotonic() - self.session.last_data > 20:
                self.disconnect(self.session.error or 'La TV ne reçoit plus la vidéo. Reconnectez-vous.')
