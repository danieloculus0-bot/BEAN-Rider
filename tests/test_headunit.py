import http.client
import json
from http.server import ThreadingHTTPServer
import sys
import threading
import unittest

from bean_rider.headunit import ProjectionManager, ReceiverCommand, load_receiver_config
from bean_rider.live import DASHBOARD_HTML, LiveConfig, LiveState, make_handler


class FakeProcess:
    def poll(self):
        return None


class HeadUnitTests(unittest.TestCase):
    def test_both_projection_apps_standard_even_without_receiver(self):
        manager = ProjectionManager()
        status = manager.status()
        self.assertEqual([item['id'] for item in status['apps']],
                         ['bean', 'carplay', 'android_auto'])
        self.assertTrue(all(item['standard'] for item in status['apps']))
        self.assertEqual(status['apps'][1]['status'], 'receiver_not_installed')
        self.assertEqual(status['apps'][2]['status'], 'receiver_not_installed')
        self.assertFalse(status['apps'][1]['projection_operational_verified'])
        self.assertIn('app-carplay', DASHBOARD_HTML)
        self.assertIn('app-android_auto', DASHBOARD_HTML)

    def test_receiver_command_needs_local_absolute_executable(self):
        with self.assertRaises(ValueError):
            ReceiverCommand('relative/receiver')
        with self.assertRaises(ValueError):
            ReceiverCommand('/bin/echo', ('bad\0arg',))
        with self.assertRaises(ValueError):
            ProjectionManager({'unknown_service': ReceiverCommand(sys.executable)})

    def test_launch_only_configured_app_without_shell(self):
        calls = []
        def fake_spawn(argv, **kwargs):
            calls.append((argv, kwargs))
            return FakeProcess()
        manager = ProjectionManager({'carplay': ReceiverCommand(sys.executable, ('--version',))},
                                    spawn=fake_spawn)
        report = manager.launch('carplay')
        self.assertEqual(report['launch'], 'receiver_process_started')
        self.assertEqual(calls[0][0], [sys.executable, '--version'])
        self.assertFalse(calls[0][1]['shell'])
        self.assertEqual(manager.launch('carplay')['launch'], 'already_running')
        self.assertEqual(len(calls), 1)
        with self.assertRaises(RuntimeError):
            manager.launch('android_auto')
        with self.assertRaises(ValueError):
            manager.launch('bean')

    def test_config_missing_and_unknown_rejected(self):
        with self.assertRaises(FileNotFoundError):
            load_receiver_config('/some/missing/receiver-config.json')

    def test_http_status_and_explicit_local_receiver_launch(self):
        calls = []
        def fake_spawn(argv, **kwargs):
            calls.append(argv)
            return FakeProcess()
        manager = ProjectionManager({'android_auto': ReceiverCommand(sys.executable)}, spawn=fake_spawn)
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(LiveState(LiveConfig()), manager))
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            c = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            c.request('GET', '/api/projection')
            response = c.getresponse()
            status = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(len(status['apps']), 3)
            c.request('POST', '/api/projection/android_auto/launch')
            response = c.getresponse(); response.read()
            self.assertEqual(response.status, 403)
            c.request('POST', '/api/projection/android_auto/launch', headers={
                'Origin': 'http://evil.example', 'X-BEAN-Cockpit': 'receiver-launch'})
            response = c.getresponse(); response.read()
            self.assertEqual(response.status, 403)
            c.request('POST', '/api/projection/android_auto/launch', headers={
                'Origin': f'http://127.0.0.1:{server.server_port}',
                'X-BEAN-Cockpit': 'receiver-launch'})
            response = c.getresponse()
            payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(payload['launch'], 'receiver_process_started')
            self.assertEqual(len(calls), 1)
            self.assertFalse(payload['projection_verified'])
            c.request('POST', '/api/projection/carplay/launch', headers={
                'X-BEAN-Cockpit': 'receiver-launch'})
            response = c.getresponse(); payload = json.loads(response.read())
            self.assertEqual(response.status, 409)
            self.assertIn('not installed', payload['error'])
            c.close()
        finally:
            server.shutdown(); server.server_close(); t.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
