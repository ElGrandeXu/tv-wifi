"""Capture GStreamer : X11 ou portail Wayland, son de sortie uniquement."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading

from dlna import TVError

PROFILES = {'1080p': (1920, 1080, 12000), '720p': (1280, 720, 5000)}
ENCODERS = {
    'nvcudah264enc': ['nvcudah264enc', 'preset=p4', 'tune=low-latency', 'gop-size=30'],
    'x264enc': ['x264enc', 'tune=zerolatency', 'speed-preset=ultrafast', 'key-int-max=30',
                'bframes=0', 'threads=4'],
}


def has_plugin(name):
    try:
        return subprocess.run(['gst-inspect-1.0', name], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=4).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def encoder_works(name):
    # Une présence dans le registre ne prouve pas que le GPU soit utilisable.
    command = ['gst-launch-1.0', '-q', 'videotestsrc', 'num-buffers=1', '!',
               'videoconvert', '!', 'video/x-raw,format=NV12,width=320,height=180', '!',
               *ENCODERS[name], 'bitrate=1000', '!', 'fakesink']
    try:
        return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=8).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def choose_encoder(mode='auto'):
    if mode not in {'auto', 'software'}:
        raise TVError('Encodeur inconnu.')
    choices = ['nvcudah264enc', 'x264enc'] if mode == 'auto' else ['x264enc']
    for name in choices:
        if has_plugin(name) and encoder_works(name):
            return name
    raise TVError('Aucun encodeur H.264 utilisable. Installez gstreamer1.0-plugins-ugly '
                  '(x264 logiciel, compatible Intel/AMD/NVIDIA). Aucun pilote ne sera modifié.')


def monitor_source():
    try:
        default = subprocess.check_output(['pactl', 'get-default-sink'], text=True, timeout=4).strip()
        sinks = json.loads(subprocess.check_output(['pactl', '-f', 'json', 'list', 'sinks'],
                                                   text=True, timeout=4))
        sources = json.loads(subprocess.check_output(['pactl', '-f', 'json', 'list', 'sources'],
                                                     text=True, timeout=4))
        sink = next(s for s in sinks if s['name'] == default)
        source = next(s for s in sources if s['name'] == sink['monitor_source']
                      and s.get('monitor_source') == sink['name'])
        name = source['name']
        if not re.fullmatch(r'[A-Za-z0-9_.:-]+', name):
            raise ValueError()
        return name
    except (OSError, ValueError, KeyError, TypeError, StopIteration, subprocess.SubprocessError):
        raise TVError('Le moniteur de la sortie audio est indisponible. Vérifiez PulseAudio / '
                      'PipeWire et pactl, ou désactivez le son. Aucun micro ne sera utilisé.') from None


def build_pipeline(source, encoder, profile='1080p', audio=None):
    if profile not in PROFILES or encoder not in ENCODERS:
        raise TVError('Profil vidéo inconnu.')
    width, height, bitrate = PROFILES[profile]
    command = ['gst-launch-1.0', '-q', *source, '!', 'queue', '!', 'videoconvert', '!',
               'videorate', '!', 'videoscale', 'add-borders=true', '!',
               f'video/x-raw,width={width},height={height},framerate=30/1,pixel-aspect-ratio=1/1,format=NV12',
               '!', *ENCODERS[encoder], f'bitrate={bitrate}', '!', 'video/x-h264,profile=baseline',
               '!', 'h264parse', 'config-interval=-1', '!', 'queue', '!', 'mux.',
               'mpegtsmux', 'name=mux', 'alignment=7', '!', 'fdsink', 'fd=1', 'sync=false']
    if audio:
        if not re.fullmatch(r'[A-Za-z0-9_.:-]+', audio):
            raise TVError('Source audio invalide.')
        if not has_plugin('pulsesrc'):
            raise TVError('Le module GStreamer pulsesrc est absent.')
        aac = next((p for p in ['avenc_aac', 'voaacenc'] if has_plugin(p)), None)
        if not aac:
            raise TVError('Encodeur AAC absent : installez gstreamer1.0-libav ou désactivez le son.')
        command += ['pulsesrc', f'device={audio}', 'do-timestamp=true', '!', 'queue', '!',
                    'audioconvert', '!', 'audioresample', '!', 'audio/x-raw,rate=48000,channels=2',
                    '!', aac, 'bitrate=128000', '!', 'aacparse', '!', 'queue', '!', 'mux.']
    return command


class Capture:
    def __init__(self, command, portal=None):
        self.command = command
        self.portal = portal
        self.pass_fds = (portal.fd,) if portal else ()

    def close(self):
        if self.portal:
            self.portal.close()


def prepare_capture(cancel, audio=False, profile='1080p', mode='auto'):
    if cancel.is_set():
        raise TVError('Connexion annulée.')
    encoder = choose_encoder(mode)
    monitor = monitor_source() if audio else None
    session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
    portal = None
    try:
        if session_type == 'wayland' or (not session_type and os.environ.get('WAYLAND_DISPLAY')):
            if not has_plugin('pipewiresrc'):
                raise TVError('Capture Wayland : installez gstreamer1.0-pipewire et un portail ScreenCast.')
            from portal import ScreenCastPortal
            portal = ScreenCastPortal(cancel)
            portal.open()
            target = f'target-object={portal.serial}' if portal.serial else f'path={portal.node}'
            source = ['pipewiresrc', f'fd={portal.fd}', target, 'do-timestamp=true', 'always-copy=true']
        else:
            if not os.environ.get('DISPLAY') or not has_plugin('ximagesrc'):
                raise TVError('Capture X11 indisponible. Ouvrez TV Wi-Fi dans une session graphique '
                              'X11 ou Wayland avec portail ScreenCast.')
            source = ['ximagesrc', 'use-damage=false', 'show-pointer=true', 'do-timestamp=true']
        command = build_pipeline(source, encoder, profile, monitor)
        if cancel.is_set():
            raise TVError('Connexion annulée.')
        return Capture(command, portal)
    except BaseException:
        if portal:
            portal.close()
        raise


def diagnostics():
    """Lecture des capacités seulement : ni sélecteur de partage ni capture."""
    return {'platform': 'linux', 'session': os.environ.get('XDG_SESSION_TYPE', 'unknown'),
            'display_available': bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')),
            'plugins': {p: has_plugin(p) for p in ['ximagesrc', 'pipewiresrc', 'nvcudah264enc',
                                                  'x264enc', 'pulsesrc', 'avenc_aac', 'voaacenc',
                                                  'mpegtsmux', 'h264parse']},
            'pactl': bool(shutil.which('pactl')), 'capture_started': False}
