import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

from bean_rider.brain import RiderBrain
from bean_rider.engine_catalog import get_family, catalog
from bean_rider.live import LiveConfig, LiveState, make_handler, collect_one
from bean_rider.obd import FakeOBDReader


class EngineCatalogTests(unittest.TestCase):
    def test_ls_and_lt_are_priority_one(self):
        first = [x['key'] for x in catalog()['families'] if x['phase'] == 1]
        self.assertEqual(first, ['gm-ls','gm-lt'])
        self.assertTrue(all(x['ecu_mapping'] == 'not_implemented' for x in catalog()['families']))
        self.assertEqual(get_family('maserati-f136').phase, 2)

    def test_unknown_profile_rejected(self):
        with self.assertRaises(ValueError):
            get_family('bogus-car')
        with self.assertRaises(ValueError):
            LiveConfig(profile='wrong')
        with self.assertRaises(ValueError):
            LiveConfig(interval_s=0)
        with self.assertRaises(ValueError):
            LiveConfig(host='0.0.0.0')


class LiveMonitoringTests(unittest.TestCase):
    def test_collect_read_only_and_bounded_history(self):
        with tempfile.TemporaryDirectory() as folder:
            state=LiveState(LiveConfig(history_points=5,profile='gm-lt'))
            with RiderBrain(Path(folder)/'log.db') as brain:
                for i in range(7):
                    reader=FakeOBDReader({'RPM': 1500+i*100},faults=[('P0300','misfire')])
                    result=collect_one(state,brain,reader)
                self.assertEqual(result['samples'], 7)
                self.assertEqual(len(result['history']),5)
                self.assertEqual(result['latest']['values']['rpm'],2100)
                self.assertEqual(result['warnings'][0]['repeat_observations'],7)
                self.assertEqual(result['ecu_writes'],0)
            with RiderBrain(Path(folder)/'log.db') as brain:
                report=brain.observe(FakeOBDReader(faults=[('P0300','misfire')]))
                self.assertEqual(report.warnings[0]['repeat_observations'],8)

    def test_http_json_and_dashboard_on_loopback(self):
        state=LiveState(LiveConfig(http_port=0))
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(state))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=4)
            c.request('GET','/api/status')
            response=c.getresponse()
            payload=json.loads(response.read())
            self.assertEqual(response.status,200)
            self.assertEqual(payload['status'],'waiting')
            self.assertEqual(payload['engine']['key'],'gm-ls')
            self.assertEqual(payload['ecu_writes'],0)
            c.request('GET','/')
            page=c.getresponse()
            self.assertIn(b'BEAN',page.read())
            c.request('GET','/bad')
            self.assertEqual(c.getresponse().status,404)
            c.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=4)

    def test_error_state_does_not_fake_new_sample(self):
        state=LiveState(LiveConfig())
        state.error('serial detached')
        snap=state.snapshot()
        self.assertEqual(snap['status'],'error')
        self.assertEqual(snap['samples'],0)

if __name__=='__main__':
    unittest.main()
