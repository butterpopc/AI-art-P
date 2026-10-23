import base64
import copy
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import urllib.error
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('novelai', ROOT / 'tools/novelai.py')
nai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nai)


def png(width, height):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' * (width + 1)) * height)) + chunk(b'IEND', b''))


class NovelAITest(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads((ROOT / 'prompts/novelai-seorin-v1.json').read_text())
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / 'image.png'
        self.calls = []
        self.fake_token = 'synthetic-test-token-not-a-real-credential'

    def transport(self, url, token, method='GET', payload=None):
        self.calls.append((url, method))
        if url == nai.SUBSCRIPTION_URL:
            return {'active': True, 'tier': 3, 'paymentProcessorData': 'must-not-be-retained'}
        p = payload['parameters']
        return {'images': [{'image': base64.b64encode(png(p['width'], p['height'])).decode(), 'index': '../../outside.png'}]}

    def test_valid_recipe(self):
        self.assertEqual(nai.validate_payload(self.payload)['model'], 'nai-diffusion-4-5-full')

    def test_no_auth_does_not_send_request(self):
        with self.assertRaises(nai.NovelAIError):
            nai.generate(self.payload, self.output, '', self.transport)
        self.assertEqual(self.calls, [])

    def test_inactive_or_non_opus_cannot_generate(self):
        for state in [{'active': False, 'tier': 3}, {'active': True, 'tier': 2}, {'active': True, 'tier': '3'}, {}]:
            calls = []
            def transport(url, token, method='GET', payload=None):
                calls.append(url)
                return state
            with self.assertRaises(nai.NovelAIError):
                nai.generate(self.payload, self.output, self.fake_token, transport)
            self.assertEqual(calls, [nai.SUBSCRIPTION_URL])

    def test_paid_or_unknown_features_fail_before_network(self):
        for field, value in [('image', 'base64'), ('reference_image_multiple', ['base64']), ('upscale', {}), ('n_samples', 2), ('steps', 29), ('width', 1536), ('steps', True)]:
            p = copy.deepcopy(self.payload)
            p['parameters'][field] = value
            with self.assertRaises(nai.NovelAIError):
                nai.generate(p, self.output, self.fake_token, self.transport)
        self.assertEqual(self.calls, [])

    def test_newer_model_refused(self):
        self.payload['model'] = 'nai-diffusion-5-full'
        with self.assertRaises(nai.NovelAIError):
            nai.generate(self.payload, self.output, self.fake_token, self.transport)
        self.assertEqual(self.calls, [])

    def test_success_saves_one_png_and_nonsecret_metadata(self):
        result = nai.generate(self.payload, self.output, self.fake_token, self.transport)
        self.assertTrue(self.output.read_bytes().startswith(b'\x89PNG'))
        metadata = self.output.with_suffix('.json').read_text()
        self.assertNotIn(self.fake_token, metadata)
        self.assertNotIn('must-not-be-retained', metadata)
        self.assertEqual(json.loads(metadata)['client_approval'], 'pending')
        self.assertEqual(self.calls, [(nai.SUBSCRIPTION_URL, 'GET'), (nai.GENERATION_URL, 'POST')])
        self.assertEqual(Path(result['image']), self.output)
        self.assertEqual({p.name for p in Path(self.tmp.name).iterdir()}, {'image.png', 'image.json'})

    def test_no_retry_when_generation_fails(self):
        def transport(url, token, method='GET', payload=None):
            self.calls.append(url)
            if url == nai.SUBSCRIPTION_URL:
                return {'active': True, 'tier': 3}
            raise nai.NovelAIError('Timeout; generation result unknown.')
        with self.assertRaises(nai.NovelAIError):
            nai.generate(self.payload, self.output, self.fake_token, transport)
        self.assertEqual(self.calls, [nai.SUBSCRIPTION_URL, nai.GENERATION_URL])
        self.assertFalse(self.output.exists())

    def test_wrong_dimensions_rejected(self):
        with self.assertRaises(nai.NovelAIError):
            nai.decode_png({'images': [{'image': base64.b64encode(png(64, 64)).decode()}]}, 832, 1216)

    def test_invalid_images_rejected(self):
        for response in [{}, {'images': []}, {'images': [{'image': 'not-base64'}]}, {'images': [{'image': base64.b64encode(b'not-png').decode()}]}]:
            with self.assertRaises(nai.NovelAIError):
                nai.decode_png(response, 832, 1216)

    def test_existing_output_never_overwritten(self):
        self.output.write_bytes(b'preserve')
        with self.assertRaises(nai.NovelAIError):
            nai.generate(self.payload, self.output, self.fake_token, self.transport)
        self.assertEqual(self.output.read_bytes(), b'preserve')
        self.assertEqual(self.calls, [])

    def test_redirect_is_refused(self):
        with self.assertRaises(nai.NovelAIError):
            nai.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com')

    def test_error_body_never_logged(self):
        opener = mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError(nai.SUBSCRIPTION_URL, 401, self.fake_token, {}, io.BytesIO(self.fake_token.encode()))
        with mock.patch.object(nai.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaises(nai.NovelAIError) as ctx:
                nai.request_json(nai.SUBSCRIPTION_URL, self.fake_token)
        self.assertNotIn(self.fake_token, str(ctx.exception))
        self.assertIn('401', str(ctx.exception))
        self.assertEqual(opener.open.call_count, 1)

    def test_unapproved_destination_refused(self):
        with mock.patch.object(nai.urllib.request, 'build_opener') as opener:
            with self.assertRaises(nai.NovelAIError):
                nai.request_json('https://example.com', self.fake_token)
            opener.assert_not_called()

    def private_fixture(self, contents=None, mode=0o600):
        path = Path(self.tmp.name) / 'test-credentials.json'
        path.write_text(json.dumps(contents if contents is not None else {
            'api_token': self.fake_token, 'email': 'dummy@example.invalid', 'password': 'dummy-only',
        }))
        path.chmod(mode)
        return path

    def test_private_file_reads_only_api_token(self):
        path = self.private_fixture()
        with mock.patch.dict(nai.os.environ, {}, clear=True):
            self.assertEqual(nai.load_token(path), self.fake_token)

    def test_environment_has_priority_over_file(self):
        with mock.patch.dict(nai.os.environ, {'NOVELAI_API_TOKEN': self.fake_token}, clear=True):
            self.assertEqual(nai.load_token(ROOT / 'must-not-read.json'), self.fake_token)

    def test_file_inside_repository_rejected(self):
        with mock.patch.dict(nai.os.environ, {}, clear=True):
            with self.assertRaises(nai.NovelAIError):
                nai.load_token(ROOT / 'must-not-create.json')

    def test_group_or_other_file_permissions_rejected(self):
        path = self.private_fixture(mode=0o640)
        with mock.patch.dict(nai.os.environ, {}, clear=True):
            with self.assertRaises(nai.NovelAIError):
                nai.load_token(path)

    def test_group_or_other_directory_permissions_rejected(self):
        path = self.private_fixture()
        path.parent.chmod(0o750)
        try:
            with mock.patch.dict(nai.os.environ, {}, clear=True):
                with self.assertRaises(nai.NovelAIError):
                    nai.load_token(path)
        finally:
            path.parent.chmod(0o700)

    def test_invalid_credentials_never_echo_values(self):
        for document in [{'api_token': '\n' + self.fake_token}, {'password': self.fake_token}, {'api_token': 123}]:
            path = self.private_fixture(document)
            with mock.patch.dict(nai.os.environ, {}, clear=True):
                with self.assertRaises(nai.NovelAIError) as ctx:
                    nai.load_token(path)
            self.assertNotIn(self.fake_token, str(ctx.exception))

    def test_dry_run_does_not_read_credentials(self):
        with mock.patch.object(nai, 'load_token') as loader, mock.patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(nai.main(['--dry-run', '--credentials-file', str(ROOT / 'must-not-read.json')]), 0)
        loader.assert_not_called()


if __name__ == '__main__':
    unittest.main()
