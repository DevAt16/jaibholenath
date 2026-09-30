import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('sync_reports',Path(__file__).parents[1]/'scripts/sync_dell_reports.py')
sync=importlib.util.module_from_spec(spec);spec.loader.exec_module(sync)


class SyncTests(unittest.TestCase):
    def fixtures(self):
        snapshot={'schema_version':1,'reports':{'candidates':[{'google_place_id':'example'}]}}
        sid=hashlib.sha256(json.dumps(snapshot,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        manifest=dict(schema_version=1,snapshot_id=sid,baseline_candidates=0,database_candidates=1,
                      overlapping_place_ids=0,added_since_baseline=1,combined_candidates=1,geography_high_priority=0)
        return manifest,snapshot

    def test_verified_snapshot_and_unchanged_second_pull(self):
        manifest,snapshot=self.fixtures();calls=[]
        def fetch(path):
            calls.append(path)
            return json.dumps(manifest if path=='latest.json' else snapshot).encode()
        with tempfile.TemporaryDirectory() as output:
            self.assertEqual(sync.sync_reports(output,fetch)['status'],'synced')
            self.assertEqual(sync.sync_reports(output,fetch)['status'],'unchanged')
            self.assertEqual(len(calls),3)

    def test_malformed_manifest_does_not_replace_pointer(self):
        manifest,snapshot=self.fixtures();manifest['snapshot_id']='../../secret'
        with tempfile.TemporaryDirectory() as output:
            pointer=Path(output)/'latest.json';pointer.write_text('{"existing":true}')
            with self.assertRaises(ValueError):sync.sync_reports(output,lambda path:json.dumps(manifest).encode())
            self.assertEqual(pointer.read_text(),'{"existing":true}')

    def test_corrupt_snapshot_preserves_previous_manifest(self):
        manifest,snapshot=self.fixtures();snapshot['reports']['candidates'].append({})
        with tempfile.TemporaryDirectory() as output:
            pointer=Path(output)/'latest.json';pointer.write_text('{"existing":true}')
            with self.assertRaises(ValueError):
                sync.sync_reports(output,lambda path:json.dumps(manifest if path=='latest.json' else snapshot).encode())
            self.assertEqual(pointer.read_text(),'{"existing":true}')


if __name__=='__main__':unittest.main()
