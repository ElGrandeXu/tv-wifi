"""Frontières non fiables : réseau DLNA et fichiers d'installation."""
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]/'common'))
import dlna


class SecurityTests(unittest.TestCase):
    def test_only_lan_addresses_allowed_in_every_url_not_just_manual_entry(self):
        for address in ['127.0.0.1', '0.0.0.0', '255.255.255.255', '192.0.2.1',
                        '198.51.100.1', '240.0.0.1', '8.8.8.8', '::1']:
            with self.subTest(address=address), self.assertRaises(dlna.TVError):
                dlna.checked_url('http://'+address+'/root.xml', address)
        for address in ['10.1.2.3', '192.168.1.10', '172.16.0.5', '169.254.2.3']:
            self.assertEqual(dlna.parse_ip(address), address)

    def test_urls_reject_control_characters_credentials_and_external_hosts(self):
        for url in ['http://10.1.2.3/\npath', 'http://10.1.2.3/ path',
                    'http://@10.1.2.3/', 'http://10.1.2.3@8.8.8.8/',
                    'http://other.local/', 'https://10.1.2.3/', 'http://10.1.2.3/#x']:
            with self.subTest(url=url), self.assertRaises(dlna.TVError):
                dlna.checked_url(url, '10.1.2.3')

    def test_xml_rejects_entities_including_utf16_and_oversized_responses(self):
        xml = '<!DOCTYPE r [<!ENTITY e "data">]><r>&e;</r>'
        for data in [xml.encode(), xml.encode('utf-16'), b'x' * 262145, b'<bad>']:
            with self.subTest(size=len(data)), patch.object(dlna.OPENER, 'open', return_value=io.BytesIO(data)), \
                    self.assertRaises(dlna.TVError):
                dlna.xml_request('http://10.1.2.3/root.xml')

    def test_soap_fault_even_with_http_200_is_not_success(self):
        xml = b'<Envelope><Body><Fault><errorCode>701</errorCode></Fault></Body></Envelope>'
        tv = dlna.TV('test', '10.1.2.3', '', 'http://10.1.2.3/control',
                     'urn:schemas-upnp-org:service:AVTransport:1')
        with patch.object(dlna.OPENER, 'open', return_value=io.BytesIO(xml)), \
                self.assertRaisesRegex(dlna.TVError, 'SOAP Fault'):
            dlna.soap(tv, 'Play', {'InstanceID': 0, 'Speed': 1})

    def test_service_namespace_cannot_inject_xml_or_headers(self):
        tv = dlna.TV('test', '10.1.2.3', '', 'http://10.1.2.3/control',
                     'urn:schemas-upnp-org:service:AVTransport:1" bad="value')
        with self.assertRaisesRegex(dlna.TVError, 'service'):
            dlna.soap(tv, 'Play', {})

    def test_ssdp_requires_actual_success_status(self):
        for status in ['HTTP/1.1 1200 NO', 'HTTP/1.1 500 error 200', 'HTTP/1.1 2000']:
            packet = (status+'\r\nLocation: http://10.1.2.3/root.xml\r\n\r\n').encode()
            self.assertIsNone(dlna.ssdp_location(packet, '10.1.2.3'))
