"""Contrat réel Gio/D-Bus du portail simulé, sur un bus privé sans écran."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]/'common'))
import dlna
from portal import ScreenCastPortal, DEST, IFACE, PATH

try:
    from gi.repository import Gio, GLib
except ImportError:
    Gio = GLib = None

XML = '''<node><interface name="org.freedesktop.portal.ScreenCast">
<method name="CreateSession"><arg type="a{sv}" direction="in"/><arg type="o" direction="out"/></method>
<method name="SelectSources"><arg type="o" direction="in"/><arg type="a{sv}" direction="in"/><arg type="o" direction="out"/></method>
<method name="Start"><arg type="o" direction="in"/><arg type="s" direction="in"/><arg type="a{sv}" direction="in"/><arg type="o" direction="out"/></method>
<method name="OpenPipeWireRemote"><arg type="o" direction="in"/><arg type="a{sv}" direction="in"/><arg type="h" direction="out"/></method>
</interface><interface name="org.freedesktop.portal.Session"><method name="Close"/></interface>
<interface name="org.freedesktop.portal.Request"><method name="Close"/></interface><interface name="org.freedesktop.DBus.Properties">
<method name="GetAll"><arg type="s" direction="in"/><arg type="a{sv}" direction="out"/></method>
</interface></node>'''


@unittest.skipUnless(Gio and shutil.which('dbus-daemon') and sys.platform == 'linux', 'Gio/bus privé indisponible')
class PortalTests(unittest.TestCase):
    def setUp(self):
        self.daemon = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address=1'],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        address = self.daemon.stdout.readline().strip()
        self.environment = patch.dict(os.environ, DBUS_SESSION_BUS_ADDRESS=address)
        self.environment.start()
        self.calls = []
        self.pending = threading.Event()
        self.deny = False
        self.source_types = 3
        self.cursor_modes = 3
        self.hold_start = False
        self.ready = threading.Event()
        self.session = '/org/freedesktop/portal/desktop/session/test/capture'
        self.pipe_read, self.pipe_write = os.pipe()
        self.context = GLib.MainContext.new()
        self.loop = GLib.MainLoop.new(self.context, False)

        def serve():
            self.context.push_thread_default()
            flags = Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
            self.connection = Gio.DBusConnection.new_for_address_sync(address, flags, None, None)
            self.connection.set_exit_on_close(False)
            self.connection.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', 'RequestName', GLib.Variant('(su)', (DEST, 0)),
                None, Gio.DBusCallFlags.NONE, 2000, None)
            introspection = Gio.DBusNodeInfo.new_for_xml(XML)
            self.request_info = introspection.interfaces[2]
            self.connection.register_object(PATH, introspection.interfaces[0], self.method, None, None)
            self.connection.register_object(PATH, introspection.interfaces[3], self.method, None, None)
            self.connection.register_object(self.session, introspection.interfaces[1], self.method, None, None)
            self.ready.set()
            self.loop.run()
            self.connection.close_sync(None)
            self.context.pop_thread_default()
        self.worker = threading.Thread(target=serve, daemon=True)
        self.worker.start()
        self.assertTrue(self.ready.wait(3))

    def method(self, connection, sender, path, interface, method, parameters, invocation):
        self.calls.append((method, parameters.unpack()))
        if method == 'GetAll':
            invocation.return_value(GLib.Variant('(a{sv})', ({
                'AvailableSourceTypes': GLib.Variant('u', self.source_types),
                'AvailableCursorModes': GLib.Variant('u', self.cursor_modes)},)))
            return
        if method == 'Close':
            invocation.return_value(None)
            return
        if method == 'OpenPipeWireRemote':
            descriptors = Gio.UnixFDList.new()
            index = descriptors.append(self.pipe_read)
            invocation.return_value_with_unix_fd_list(GLib.Variant('(h)', (index,)), descriptors)
            return
        args = parameters.unpack()
        options = args[-1]
        token = options['handle_token']
        owner = sender[1:].replace('.', '_')
        handle = f'/org/freedesktop/portal/desktop/request/{owner}/{token}'
        self.connection.register_object(handle, self.request_info, self.method, None, None)
        if method == 'CreateSession':
            results = {'session_handle': GLib.Variant('s', self.session)}
        elif method == 'Start':
            results = {'streams': GLib.Variant('a(ua{sv})', [(42, {'pipewire-serial': GLib.Variant('t', 9876)})])}
        else:
            results = {}
        # Émettre avant le retour reproduit la course visée par la souscription précoce.
        if not (method == 'Start' and self.hold_start):
            code = 1 if self.deny and method == 'Start' else 0
            self.connection.emit_signal(sender, handle, 'org.freedesktop.portal.Request', 'Response',
                                        GLib.Variant('(ua{sv})', (code, results)))
        else:
            self.pending.set()
        invocation.return_value(GLib.Variant('(o)', (handle,)))

    def tearDown(self):
        self.loop.quit()
        self.context.wakeup()
        self.worker.join(timeout=3)
        os.close(self.pipe_read)
        os.close(self.pipe_write)
        self.environment.stop()
        self.daemon.terminate()
        self.daemon.communicate(timeout=3)

    def test_roundtrip_uses_permission_methods_and_receives_actual_unix_fd(self):
        portal = ScreenCastPortal(threading.Event())
        try:
            portal.open()
            self.assertEqual(portal.node, 42)
            self.assertEqual(portal.serial, 9876)
            os.write(self.pipe_write, b'test')
            self.assertEqual(os.read(portal.fd, 4), b'test')
            old_fd = portal.fd
            select = next(args for method, args in self.calls if method == 'SelectSources')
            self.assertFalse(select[1]['multiple'])
            self.assertEqual(select[1]['cursor_mode'], 2)
            self.assertNotIn('restore_token', select[1])
        finally:
            portal.close()
            portal.close()
        with self.assertRaises(OSError):
            os.fstat(old_fd)
        self.assertEqual([c[0] for c in self.calls], ['CreateSession', 'GetAll', 'SelectSources', 'Start', 'OpenPipeWireRemote', 'Close'])


    def test_monitor_only_backend_and_hidden_cursor_fallback_are_respected(self):
        self.source_types = 1
        self.cursor_modes = 1
        portal = ScreenCastPortal(threading.Event())
        try:
            portal.open()
            options = next(args[-1] for method, args in self.calls if method == 'SelectSources')
            self.assertEqual(options['types'], 1)
            self.assertNotIn('cursor_mode', options)
        finally:
            portal.close()

    def test_system_revocation_signals_cancellation_without_waiting_for_video_timeout(self):
        cancel = threading.Event()
        portal = ScreenCastPortal(cancel)
        portal.open()
        try:
            self.connection.emit_signal(None, self.session, 'org.freedesktop.portal.Session',
                                        'Closed', GLib.Variant('(a{sv})', ({},)))
            self.assertTrue(cancel.wait(2))
        finally:
            portal.close()

    def test_denial_closes_session_without_opening_pipewire(self):
        self.deny = True
        portal = ScreenCastPortal(threading.Event())
        with self.assertRaisesRegex(dlna.TVError, 'refusé'):
            portal.open()
        self.assertTrue(portal.closed)
        self.assertNotIn('OpenPipeWireRemote', [c[0] for c in self.calls])

    def test_cancel_closes_pending_request_and_session(self):
        self.hold_start = True
        cancel = threading.Event()
        portal = ScreenCastPortal(cancel)
        errors = []
        def open_portal():
            try:
                portal.open()
            except Exception as error:
                errors.append(error)
        thread = threading.Thread(target=open_portal)
        thread.start()
        self.assertTrue(self.pending.wait(3))
        cancel.set()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertTrue(errors and isinstance(errors[0], dlna.TVError))
        self.assertEqual([c[0] for c in self.calls].count('Close'), 2)
        self.assertTrue(portal.closed)
