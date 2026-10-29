"""Scénario GTK sur affichage virtuel : aucune TV, capture ou préférence réelle."""
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'linux'))
import tv_wifi
import dlna
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gio


class FakeSession:
    created = []
    hold = True

    def __init__(self, tv, cancel, *args):
        self.tv, self.cancel = tv, cancel
        self.last_data = time.monotonic()
        self.error = None
        self.closed = False
        self.entered = threading.Event()
        self.created.append(self)

    def start(self):
        self.entered.set()
        if self.hold:
            if not self.cancel.wait(3):
                raise AssertionError('Le bouton d’annulation n’a pas annulé la connexion.')
            raise dlna.TVError('Connexion annulée.')

    def stop(self):
        self.cancel.set()
        self.closed = True


def main():
    tv = dlna.TV('TV simulée', '192.168.1.20', '', '', '')
    fake_capture = SimpleNamespace(command=['never-executed'], pass_fds=(), close=lambda: None)
    with tempfile.TemporaryDirectory() as folder, patch.object(dlna, 'PREFS', Path(folder)/'prefs.json'), \
            patch.object(tv_wifi, 'discover', return_value=[]), \
            patch.object(tv_wifi, 'resolve_tv', return_value=tv), \
            patch.object(tv_wifi, 'CastSession', FakeSession), \
            patch.object(tv_wifi, 'prepare_capture', return_value=fake_capture) as capture:
        app = tv_wifi.create_application()
        app.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
        errors = []
        stage = 0
        deadline = time.monotonic() + 8
        def check():
            nonlocal stage
            try:
                assert time.monotonic() < deadline, ('Délai dépassé', stage)
                if stage == 0:
                    if not app.window or app.busy:
                        return True
                    assert app.window.get_visible()
                    assert not app.switch.get_active() and not app.audio.get_active()
                    assert app.quality.get_active_id() == '1080p'
                    assert app.session is None and not capture.called
                    app.entry.set_text('bad-ip')
                    app.switch.set_active(True)
                    assert not capture.called and not app.switch.get_active()
                    app.entry.set_text(tv.ip)
                    app.switch.set_active(True)
                    stage = 1
                elif stage == 1:
                    if not FakeSession.created or not FakeSession.created[0].entered.is_set():
                        return True
                    assert app.busy and app.switch.get_sensitive()
                    app.switch.set_active(False)
                    stage = 2
                elif stage == 2:
                    if app.busy:
                        return True
                    assert app.session is None and not app.switch.get_active()
                    assert FakeSession.created[0].closed
                    FakeSession.hold = False
                    app.switch.set_active(True)
                    stage = 3
                elif stage == 3:
                    if app.busy:
                        return True
                    assert app.session is not None and app.switch.get_active()
                    assert not app.audio.get_sensitive() and not app.entry.get_sensitive()
                    assert not app.audio.get_active()
                    stage = 4
                    app.window.close()
                    return False
                return True
            except BaseException as error:
                errors.append(error)
                app.quit()
                return False
        GLib.timeout_add(50, check)
        result = app.run([])
        assert result == 0, result
        assert not errors, errors
        assert stage == 4, stage
        assert FakeSession.created and all(s.closed for s in FakeSession.created)
        print('GTK: ouverture, IP invalide, annulation, reconnexion, fermeture ; aucune capture réelle.')


if __name__ == '__main__':
    main()
