import kubecert
from effect.testing import perform_sequence


def return_none(x):
    pass


def test_create_ca():
    seq = [
        (
            kubecert.CreateDirectory(
                '/test',
                create_parents=True
            ),
            return_none
        ),
        (
            kubecert.GenerateRSAKey(
                path='/test/ca-key.pem'
            ),
            return_none
        ),
        (
            kubecert.GenerateCACertificate(
                path='/test/ca-crt.pem',
                key_path='/test/ca-key.pem',
                common_name='common.name',
            ),
            return_none,
        ),
    ]
    eff = kubecert.generate_ca(
        output_path='/test',
        common_name='common.name'
    )
    perform_sequence(seq, eff)


def test_create_client_cert():
    seq = [
        (
            kubecert.CreateDirectory(
                path='/cert',
                create_parents=True,
            ),
            return_none
        ),
        (
            kubecert.GenerateRSAKey(
                path='/cert/key.pem'
            ),
            return_none
        ),
        (
            kubecert.GenerateOpenSSLConfig(
                path='/cert/openssl.conf',
                kind='client'
            ),
            return_none
        ),
        (
            kubecert.GenerateCSR(
                output_path='/cert/csr.pem',
                config_path='/cert/openssl.conf',
                common_name='common.name',
                key_path='/cert/key.pem'
            ),
            return_none
        ),
        (
            kubecert.SignCertificate(
                csr_path='/cert/csr.pem',
                ca_cert_path='/ca/ca-crt.pem',
                ca_key_path='/ca/ca-key.pem',
                output_path='/cert/crt.pem',
                config_path='/cert/openssl.conf',
            ),
            return_none
        )
    ]
    eff = kubecert.generate_cert(
        ca_path='/ca',
        outpath='/cert',
        common_name='common.name',
        kind='client',
    )
    perform_sequence(seq, eff)


def test_create_server_cert():
    seq = [
        (
            kubecert.CreateDirectory(
                path='/cert',
                create_parents=True,
            ),
            return_none
        ),
        (
            kubecert.GenerateRSAKey(
                path='/cert/key.pem'
            ),
            return_none,
        ),
        (
            kubecert.GenerateOpenSSLConfig(
                path='/cert/openssl.conf',
                kind='server'
            ),
            return_none
        ),
        (
            kubecert.ReplaceStringInFile(
                path='/cert/openssl.conf',
                placeholder='# additional names.*',
                entry_string='IP.3 = 1.2.3.4',
            ),
            return_none
        ),
        (
            kubecert.GenerateCSR(
                output_path='/cert/csr.pem',
                config_path='/cert/openssl.conf',
                common_name='common.name',
                key_path='/cert/key.pem'
            ),
            return_none
        ),
        (
            kubecert.SignCertificate(
                csr_path='/cert/csr.pem',
                ca_cert_path='/ca/ca-crt.pem',
                ca_key_path='/ca/ca-key.pem',
                output_path='/cert/crt.pem',
                config_path='/cert/openssl.conf',
            ),
            return_none
        )
    ]
    eff = kubecert.generate_cert(
        ca_path='/ca',
        outpath='/cert',
        common_name='common.name',
        kind='server',
        server_ip='1.2.3.4',
    )
    perform_sequence(seq, eff)
