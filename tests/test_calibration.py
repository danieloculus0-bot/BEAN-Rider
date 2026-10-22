from pathlib import Path
import tempfile
import unittest

from bean_rider.calibration import (CalibrationMap, compare_maps, load_map_json,
                                    save_map_json, inspect_msq, load_msq_map)
from bean_rider.profiles import EXAMPLE_PROFILES, REFERENCE_ECOSYSTEMS

MSQ = '''<?xml version="1.0"?>
<msq xmlns="http://www.msefi.com/:msq"><versionInfo signature="speeduino 202501" firmwareInfo="Speeduino+2025.01.1"/>
<page><pcVariable name="rpmBins" rows="1" cols="3">1000 2000 3000</pcVariable>
<pcVariable name="loadBins" rows="2" cols="1">30 100</pcVariable>
<pcVariable name="fuelTable" rows="2" cols="3" units="%">40 50 60 70 80 90</pcVariable></page></msq>'''


class CalibrationTests(unittest.TestCase):
    def example(self):
        return CalibrationMap('fuelVE', 'test_engine', 'test_ecu', 'rpm', 'kPa', '%',
                              (1000,2000,3000),(30,100), ((40,50,60),(70,80,90)))

    def test_interpolation_and_no_extrapolation(self):
        m=self.example()
        self.assertEqual(m.sample(1500,65),60)
        with self.assertRaises(ValueError):m.sample(3300,90)

    def test_edit_is_copy_and_diff_is_traceable(self):
        a=self.example()
        b=a.edit(1,0,49)
        self.assertEqual(a.values[0][1],50)
        diff=compare_maps(a,b)
        self.assertEqual(diff['changed_cells'],1)
        self.assertEqual(diff['changes'][0]['delta'],-1)
        self.assertNotEqual(a.fingerprint(),b.fingerprint())

    def test_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            f=Path(directory)/'table.json'
            m=self.example()
            save_map_json(m,f)
            self.assertEqual(load_map_json(f).fingerprint(),m.fingerprint())

    def test_strict_axes_rejected(self):
        with self.assertRaises(ValueError):
            CalibrationMap('X','engine','ecu','rpm','load','%',(1000,1000),(30,80),((1,2),(3,4)))

    def test_msq_inspection_and_explicit_numeric_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            f=Path(directory)/'speeduino.msq'
            f.write_text(MSQ)
            view=inspect_msq(f)
            self.assertEqual(view['firmware'],'Speeduino+2025.01.1')
            self.assertEqual(len(view['tables']),3)
            self.assertFalse(view['values_exported'])
            m=load_msq_map(f,table='fuelTable',x_variable='rpmBins',y_variable='loadBins',
                           profile='test_engine',ecu_family='speeduino',x_unit='rpm',
                           y_unit='kPa',value_unit='%')
            self.assertEqual(m.sample(2000,100),80)
            self.assertTrue(m.source.startswith('imported_msq_sha256:'))

    def test_msq_wrong_axis_and_dtd_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            f=Path(directory)/'bad.msq'
            f.write_text(MSQ.replace('30 100','30 80 100'))
            with self.assertRaises(ValueError):
                load_msq_map(f,table='fuelTable',x_variable='rpmBins',y_variable='loadBins',
                             profile='engine',ecu_family='speeduino',x_unit='rpm',y_unit='kPa',value_unit='%')
            f.write_text('<!DOCTYPE msq [ <!ENTITY foo SYSTEM "file:///etc/passwd"> ]><msq />')
            with self.assertRaises(ValueError): inspect_msq(f)

    def test_profiles_are_not_universal_ecu_writers(self):
        self.assertFalse(EXAMPLE_PROFILES['maserati-f136-4.7'].supports_calibration_write)
        self.assertEqual({r['name'] for r in REFERENCE_ECOSYSTEMS}, {'Speeduino','rusEFI'})

if __name__ == '__main__': unittest.main()
