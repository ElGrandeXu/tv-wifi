#!/usr/bin/env python3
"""Interface GTK de TV Wi-Fi ; aucune diffusion sans activation explicite."""
import os
from pathlib import Path
import signal
import sys
import threading
import time

# Les archives embarquent dlna.py ; le checkout conserve une seule source commune.
if (Path(__file__).resolve().parents[1] / 'common').is_dir():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from dlna import TV, TVError, CastSession, parse_ip, checked_url, load_preferences, save_preferences, discover, resolve_tv
from linux_backend import prepare_capture, diagnostics

def create_application():
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gio, GLib

    class Application(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='org.marc.TVWifi', flags=Gio.ApplicationFlags.FLAGS_NONE)
            self.window = None
            self.session = None
            self.cancel = threading.Event()
            self.busy = False
            self.connecting = False
            self.closing = False
            self.updating = False
            self.known = []
            self.searching = False
            self.search_cancel = threading.Event()

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Gtk.ApplicationWindow(application=self, title='TV Wi-Fi')
            self.window.set_default_size(530, 350)
            self.window.set_border_width(22)
            self.window.connect('delete-event', self.on_close)
            layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            self.window.add(layout)
            heading = Gtk.Label(xalign=0)
            heading.set_markup('<big><b>Votre écran sur la TV</b></big>')
            layout.pack_start(heading, False, False, 0)
            layout.pack_start(Gtk.Label(label='Vidéo H.264 · Son du système en option', xalign=0), False, False, 0)
            row = Gtk.Box(spacing=8)
            self.combo = Gtk.ComboBoxText()
            self.combo.set_hexpand(True)
            self.combo.connect('changed', self.on_selected)
            self.search = Gtk.Button(label='Rechercher les TV')
            self.search.connect('clicked', lambda *_: self.search_tvs())
            row.pack_start(self.combo, True, True, 0)
            row.pack_start(self.search, False, False, 0)
            layout.pack_start(row, False, False, 0)
            self.entry = Gtk.Entry()
            self.entry.set_placeholder_text('Ou saisissez l’adresse IP de la TV')
            self.entry.set_input_purpose(Gtk.InputPurpose.FREE_FORM)
            prefs = load_preferences()
            self.entry.set_text(str(prefs.get('last_ip', '')))
            try:
                remembered = TV(**prefs['last_tv'])
                checked_url(remembered.location, remembered.ip)
                self.known.append(remembered)
            except (KeyError, TypeError, TVError):
                pass
            layout.pack_start(self.entry, False, False, 0)
            self.audio = Gtk.CheckButton(label='Partager aussi le son du système (pas le micro)')
            layout.pack_start(self.audio, False, False, 0)
            options = Gtk.Box(spacing=12)
            self.quality = Gtk.ComboBoxText()
            self.quality.append('1080p', 'Full HD 1080p')
            self.quality.append('720p', '720p — réseau ou ordinateur lent')
            self.quality.set_active_id('1080p')
            self.software = Gtk.CheckButton(label='Sans GPU (compatible)')
            options.pack_start(self.quality, True, True, 0)
            options.pack_start(self.software, False, False, 0)
            layout.pack_start(options, False, False, 0)
            connect_row = Gtk.Box(spacing=12)
            self.connection_label = Gtk.Label(label='Diffusion de l’écran', xalign=0)
            self.switch = Gtk.Switch()
            self.switch.set_valign(Gtk.Align.CENTER)
            self.switch.connect('state-set', self.on_switch)
            connect_row.pack_start(self.connection_label, True, True, 0)
            connect_row.pack_end(self.switch, False, False, 0)
            layout.pack_start(connect_row, False, False, 2)
            self.status = Gtk.Label(label='Choisissez la TV de votre salle, puis activez la diffusion.', xalign=0)
            self.status.set_line_wrap(True)
            self.status.set_selectable(True)
            layout.pack_start(self.status, False, False, 0)
            note = Gtk.Label(label='Même réseau que la TV · Plusieurs secondes de décalage possibles.\n'
                             'X11 : tout le bureau. Wayland : sélection dans la fenêtre système.\n'
                             'Fermer cette fenêtre coupe la diffusion. Évitez les contenus privés.', xalign=0)
            note.set_line_wrap(True)
            note.get_style_context().add_class('dim-label')
            layout.pack_start(note, False, False, 0)
            self.window.show_all()
            GLib.timeout_add_seconds(1, self.monitor)
            def stop_signal():
                if not self.on_close():
                    self.window.destroy()
                return False
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, stop_signal)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, stop_signal)
            self.busy = True
            self.update_controls()

            GLib.idle_add(self.ready)

        def ready(self):
            self.busy = False
            if self.closing:
                self.window.destroy()
                return False
            self.update_controls()
            self.search_tvs()
            return False

        def update_controls(self):
            on = self.session is not None or self.connecting
            self.updating = True
            self.switch.set_state(on)
            self.switch.set_active(on)
            self.updating = False
            self.switch.set_sensitive(not self.busy or self.connecting)
            self.entry.set_sensitive(not on and not self.busy)
            self.combo.set_sensitive(not on and not self.busy)
            self.search.set_sensitive(not on and not self.busy and not self.searching)
            for control in [self.audio, self.quality, self.software]:
                control.set_sensitive(not on and not self.busy)

        def search_tvs(self):
            if self.busy or self.closing or self.searching:
                return
            self.searching = True
            self.search.set_sensitive(False)
            self.search.set_label('Recherche…')
            def worker():
                try:
                    found, error = discover(cancel=self.search_cancel), None
                except Exception as exc:
                    found, error = [], str(exc)
                GLib.idle_add(self.searched, found, error)
            threading.Thread(target=worker, daemon=True).start()

        def searched(self, found, error):
            if self.closing:
                return False
            self.searching = False
            self.combo.remove_all()
            by_ip = {tv.ip: tv for tv in self.known}
            by_ip.update({tv.ip: tv for tv in found})
            self.known = list(by_ip.values())
            for tv in found:
                self.combo.append(tv.ip, f'{tv.name} — {tv.ip}')
            self.search.set_label('Rechercher les TV')
            self.search.set_sensitive(not self.busy and not self.session)
            if not self.session and not self.busy:
                self.status.set_text(error or (f'{len(found)} TV disponible(s). Choisissez celle de votre salle.'
                                               if found else 'Aucune TV détectée. Essayez son adresse IP ou relancez la recherche.'))
            return False

        def on_selected(self, combo):
            if not self.session:
                ip = combo.get_active_id()
                if ip:
                    self.entry.set_text(ip)

        def on_switch(self, widget, active):
            if self.updating:
                return True
            if self.busy:
                if self.connecting and not active:
                    self.cancel.set()
                    self.status.set_text('Annulation de la connexion…')
                return True
            if active:
                try:
                    ip = parse_ip(self.entry.get_text())
                except TVError as exc:
                    self.status.set_text(str(exc))
                    self.update_controls()
                    return True
                self.cancel = threading.Event()
                self.busy = True
                self.connecting = True
                self.status.set_text('Connexion à ' + ip + '…')
                self.update_controls()
                known = list(self.known)
                audio = self.audio.get_active()
                profile = self.quality.get_active_id()
                mode = 'software' if self.software.get_active() else 'auto'
                def connect():
                    session = None
                    capture = None
                    try:
                        tv = resolve_tv(ip, known, self.cancel)
                        capture = prepare_capture(self.cancel, audio, profile, mode)
                        session = CastSession(tv, self.cancel, capture.command,
                                              capture.pass_fds, capture.close)
                        session.start()
                        GLib.idle_add(self.connected, session)
                    except Exception as exc:
                        if session:
                            session.stop()
                        elif capture:
                            capture.close()
                        GLib.idle_add(self.failed, str(exc))
                threading.Thread(target=connect, daemon=False).start()
            else:
                self.disconnect()
            return True

        def connected(self, session):
            self.busy = False
            self.connecting = False
            self.session = session
            if self.closing or session.cancel.is_set():
                self.disconnect()
                return False
            try:
                save_preferences(session.tv)
            except OSError:
                pass  # Une préférence non sauvegardée ne doit pas couper le cours.
            self.status.set_text('Connecté à ' + session.tv.name + ' — ' + session.tv.ip)
            self.update_controls()
            return False

        def failed(self, message):
            self.busy = False
            self.connecting = False
            self.session = None
            if self.closing:
                self.window.destroy()
            else:
                self.status.set_text(message)
                self.update_controls()
            return False

        def disconnect(self, reason=None):
            self.cancel.set()
            self.busy = True
            self.status.set_text('Déconnexion…')
            self.update_controls()
            session = self.session
            def worker():
                error = None
                try:
                    if session:
                        session.stop()
                except Exception as exc:
                    error = str(exc)
                GLib.idle_add(self.disconnected, reason or error)
            threading.Thread(target=worker, daemon=False).start()

        def disconnected(self, message):
            self.session = None
            self.busy = False
            if self.closing:
                self.window.destroy()
            else:
                self.status.set_text(message or 'Déconnecté. Votre écran n’est plus partagé.')
                self.update_controls()
            return False

        def monitor(self):
            if self.session and not self.busy:
                if self.session.cancel.is_set():
                    self.disconnect('Le partage a été arrêté ou révoqué dans le système.')
                elif self.session.error or time.monotonic() - self.session.last_data > 20:
                    self.disconnect(self.session.error or 'La TV ne reçoit plus la vidéo. Reconnectez-vous.')
            return not self.closing

        def on_close(self, *unused):
            self.closing = True
            self.cancel.set()
            self.search_cancel.set()
            if self.busy:
                self.status.set_text('Arrêt de la diffusion…')
            elif self.session:
                self.disconnect()
            else:
                return False
            return True

    return Application()


def run_gui():
    application = create_application()
    return application.run(None)


if __name__ == '__main__':
    if sys.argv[1:] == ['--diagnose']:
        import json
        print(json.dumps(diagnostics(), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    raise SystemExit(run_gui())
