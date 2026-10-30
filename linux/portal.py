"""XDG ScreenCast via Gio, avec consentement système et connexion D-Bus dédiée."""
import os
import secrets
import threading
import time

from dlna import TVError

DEST = 'org.freedesktop.portal.Desktop'
PATH = '/org/freedesktop/portal/desktop'
IFACE = 'org.freedesktop.portal.ScreenCast'


class ScreenCastPortal:
    def __init__(self, cancel):
        self.cancel = cancel
        self.connection = None
        self.session = None
        self.fd = None
        self.node = None
        self.serial = None
        self.closed = False
        self.lock = threading.Lock()
        self.watch_stop = threading.Event()
        self.watcher = None

    def request(self, method, signature, args, options):
        Gio, GLib = self.Gio, self.GLib
        token = 'tvwifi' + secrets.token_hex(12)
        options = dict(options, handle_token=GLib.Variant('s', token))
        sender = self.connection.get_unique_name()[1:].replace('.', '_')
        handle = f'/org/freedesktop/portal/desktop/request/{sender}/{token}'
        response = []
        subscription = self.connection.signal_subscribe(
            DEST, 'org.freedesktop.portal.Request', 'Response', handle, None,
            Gio.DBusSignalFlags.NONE, lambda *a: response.append(a[5].unpack()))
        try:
            result = self.connection.call_sync(DEST, PATH, IFACE, method,
                GLib.Variant(signature, (*args, options)), GLib.VariantType.new('(o)'),
                Gio.DBusCallFlags.NONE, 5000, None)
            if result.unpack()[0] != handle:
                raise TVError('Le portail ScreenCast renvoie un identifiant de requête incohérent.')
            deadline = time.monotonic() + 120
            while not response:
                while self.context.pending():
                    self.context.iteration(False)
                if self.cancel.is_set() or time.monotonic() >= deadline:
                    self.connection.call_sync(DEST, handle, 'org.freedesktop.portal.Request', 'Close',
                        None, None, Gio.DBusCallFlags.NONE, 2000, None)
                    raise TVError('Sélection d’écran annulée ou délai du portail dépassé.')
                if not response:
                    self.cancel.wait(.05)
            code, values = response[0]
            if code != 0:
                raise TVError('Le partage d’écran a été refusé ou annulé dans le portail système.')
            return values
        finally:
            self.connection.signal_unsubscribe(subscription)

    def open(self):
        import gi
        from gi.repository import Gio, GLib
        self.Gio, self.GLib = Gio, GLib
        self.context = GLib.MainContext.new()
        self.context.push_thread_default()
        try:
            address = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
            flags = Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
            self.connection = Gio.DBusConnection.new_for_address_sync(address, flags, None, None)
            self.connection.set_exit_on_close(False)
            values = self.request('CreateSession', '(a{sv})', (), {
                'session_handle_token': GLib.Variant('s', 'tvwifi' + secrets.token_hex(12))})
            self.session = values['session_handle']
            self.connection.signal_subscribe(DEST, 'org.freedesktop.portal.Session', 'Closed',
                self.session, None, Gio.DBusSignalFlags.NONE, lambda *a: self.cancel.set())
            properties = self.connection.call_sync(DEST, PATH, 'org.freedesktop.DBus.Properties',
                'GetAll', GLib.Variant('(s)', (IFACE,)), GLib.VariantType.new('(a{sv})'),
                Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
            source_types = int(properties.get('AvailableSourceTypes', 1)) & 3
            if not source_types:
                raise TVError('Ce portail ne propose ni écran ni fenêtre à partager.')
            options = {'types': GLib.Variant('u', source_types), 'multiple': GLib.Variant('b', False)}
            # Le portail masque le pointeur par défaut : l'intégrer si le backend le permet.
            if int(properties.get('AvailableCursorModes', 0)) & 2:
                options['cursor_mode'] = GLib.Variant('u', 2)
            # Pas de restauration silencieuse ; le portail choisit écran ou fenêtre.
            self.request('SelectSources', '(oa{sv})', (self.session,), options)
            values = self.request('Start', '(osa{sv})', (self.session, ''), {})
            streams = values.get('streams', [])
            if len(streams) != 1 or not isinstance(streams[0][0], int) or streams[0][0] < 1:
                raise TVError('Le portail ne fournit pas de flux vidéo unique.')
            self.node = streams[0][0]
            serial = streams[0][1].get('pipewire-serial')
            if isinstance(serial, int) and serial > 0:
                self.serial = serial
            result, fds = self.connection.call_with_unix_fd_list_sync(
                DEST, PATH, IFACE, 'OpenPipeWireRemote', GLib.Variant('(oa{sv})', (self.session, {})),
                GLib.VariantType.new('(h)'), Gio.DBusCallFlags.NONE, 5000, None, None)
            self.fd = fds.get(result.unpack()[0])
            def watch():
                while not self.watch_stop.is_set():
                    while self.context.pending():
                        self.context.iteration(False)
                    if self.connection.is_closed():
                        self.cancel.set()
                        return
                    self.watch_stop.wait(.1)
            self.watcher = threading.Thread(target=watch, daemon=True)
        except Exception as error:
            self.close()
            if isinstance(error, TVError):
                raise
            raise TVError('Capture Wayland indisponible : vérifiez xdg-desktop-portal et le '
                          'backend ScreenCast de votre bureau. ' + str(error)) from None
        finally:
            self.context.pop_thread_default()
        # Le contexte n'est acquis par le surveillant qu'après son transfert.
        self.watcher.start()

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.watch_stop.set()
            if self.watcher and self.watcher.ident:
                self.watcher.join(timeout=2)
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            if self.connection:
                try:
                    if self.session:
                        self.connection.call_sync(DEST, self.session, 'org.freedesktop.portal.Session',
                            'Close', None, None, self.Gio.DBusCallFlags.NONE, 2000, None)
                except Exception:
                    pass
                finally:
                    try:
                        self.connection.close_sync(None)
                    except Exception:
                        pass
