#!/usr/bin/env python3

import argparse
import os
import os.path
import subprocess

import attr
from effect import (ComposedDispatcher, Effect, TypeDispatcher,
                    base_dispatcher, sync_perform, sync_performer)
from effect.do import do
from effect.io import stdio_dispatcher


def dispatcher():
    return ComposedDispatcher([
        base_dispatcher,
        stdio_dispatcher,
        TypeDispatcher({
            RunCommand: run_command_performer,
            CreateDirectory: create_directory_performer,
            GenerateRSAKey: generate_rsa_key_performer,
            GenerateCACertificate: generate_ca_certificate_performer,
            GenerateOpenSSLConfig: generate_openssl_config_performer,
            GenerateCSR: generate_csr_performer,
            SignCertificate: sign_certificate_performer,
            ReplaceStringInFile: replace_string_in_file_performer,
        }),
    ])


@attr.s
class ReplaceStringInFile(object):
    path = attr.ib()
    placeholder = attr.ib()
    entry_string = attr.ib()


@sync_performer
def replace_string_in_file_performer(dispatcher, intent):
    with open(intent.path, 'r') as f:
        file_content = f.read()

    with open(intent.path, 'w') as f:
        f.write(file_content.replace(
            intent.placeholder,
            intent.entry_string
        ))


@attr.s
class RunCommand(object):
    cmd = attr.ib()
    dry_run = attr.ib(default=False)
    stdin = attr.ib(default=None)
    stdout = attr.ib(default=None)


@sync_performer
def run_command_performer(dispatcher, intent):
    cmd = intent.cmd
    stdin = intent.stdin
    stdout = intent.stdout
    dry_run = intent.dry_run
    if dry_run:
        print(cmd)
        return None
    else:
        if stdin is None:
            return subprocess.run(cmd, shell=True)
        else:
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=stdout,
                universal_newlines=True,
            )
            proc.stdin.write(stdin)
            return proc.communicate()


@attr.s
class CreateDirectory(object):
    path = attr.ib()
    create_parents = attr.ib(default=False)


@sync_performer
def create_directory_performer(dispatcher, intent):
    if intent.create_parents:
        os.makedirs(intent.path, exist_ok=True)
    else:
        os.mkdir(intent.path)


@attr.s
class GenerateCACertificate(object):
    path = attr.ib()
    common_name = attr.ib()
    key_path = attr.ib()


@sync_performer
def generate_ca_certificate_performer(dispatcher, intent):
    return Effect(RunCommand(
        cmd=(
            'openssl req -x509 -new -nodes -key {key} -days 10000 -out {out} '
            '-subj "/CN={cn}"'
        ).format(
            key=intent.key_path,
            out=intent.path,
            cn=intent.common_name
        ),
    ))


@attr.s
class GenerateRSAKey(object):
    path = attr.ib()


@sync_performer
def generate_rsa_key_performer(dispatcher, intent):
    return Effect(RunCommand(
        cmd="openssl genrsa -out {out} 2048".format(
            out=intent.path,
        ),
    ))


@attr.s
class GenerateCert(object):
    dry_run = attr.ib()
    ca_path = attr.ib()
    outname = attr.ib()
    common_name = attr.ib()
    kind = attr.ib()
    server_ip = attr.ib()


@attr.s
class GenerateOpenSSLConfig(object):
    path = attr.ib()
    kind = attr.ib()


@sync_performer
def generate_openssl_config_performer(dispatcher, intent):

    if intent.kind == 'client':
        template_path = os.path.join(
            configs_path(), "client-openssl.conf"
        )
    else:
        template_path = os.path.join(
            configs_path(), "server-openssl.conf"
        )

    target_path = intent.path

    with open(target_path, 'w') as target_file:
        with open(template_path, 'r') as source_file:
            target_file.write(source_file.read())


@attr.s
class GenerateCSR(object):
    output_path = attr.ib()
    key_path = attr.ib()
    common_name = attr.ib()
    config_path = attr.ib()


@sync_performer
def generate_csr_performer(dispatcher, intent):
    return Effect(RunCommand(
        (
            'openssl req -new -key {keypath} -out {outpath} -subj '
            '"/CN={common_name}" -config {config}'
        ).format(
            keypath=intent.key_path,
            outpath=intent.output_path,
            common_name=intent.common_name,
            config=intent.config_path,
        )
    ))


@attr.s
class SignCertificate(object):
    csr_path = attr.ib()
    ca_cert_path = attr.ib()
    ca_key_path = attr.ib()
    output_path = attr.ib()
    config_path = attr.ib()


@sync_performer
def sign_certificate_performer(dispatcher, intent):
    return Effect(RunCommand(
        (
            'openssl x509 -req -in {csrpath} -CA {cacert} -CAkey {cakey} '
            '-CAcreateserial -out {outpath} -days 365 -extensions v3_req '
            '-extfile {confpath}'
        ).format(
            csrpath=intent.csr_path,
            cacert=intent.ca_cert_path,
            cakey=intent.ca_key_path,
            outpath=intent.output_path,
            confpath=intent.config_path
        )))


@do
def generate_ca(output_path, common_name, dry_run=False):
    yield Effect(CreateDirectory(
        path=output_path,
        create_parents=True,
    ))
    yield Effect(GenerateRSAKey(
        path=os.path.join(output_path, 'ca-key.pem')
    ))
    return Effect(GenerateCACertificate(
        path=os.path.join(output_path, 'ca-crt.pem'),
        key_path=os.path.join(output_path, 'ca-key.pem'),
        common_name=common_name
    ))


@do
def generate_cert(
        ca_path,
        outpath,
        common_name,
        kind,
        additional_addresses=[],
        additional_names=[],
        dry_run=False
):
    # generate certificate key
    yield Effect(CreateDirectory(
        path=outpath,
        create_parents=True
    ))

    key_path = os.path.join(outpath, 'key.pem')

    yield Effect(GenerateRSAKey(path=key_path))

    config_path = os.path.join(outpath, 'openssl.conf')

    yield Effect(GenerateOpenSSLConfig(
        path=config_path,
        kind=kind,
    ))

    if additional_addresses or additional_names:
        additional_dns_entries = '\n'.join([
            'DNS.{n} = {name}'.format(
                n=n,
                name=name,
            ) for name, n
            in zip(
                additional_names,
                range(3, len(additional_names) + 3)
            )
        ])
        additional_address_entries = '\n'.join([
            'IP.{n} = {address}'.format(
                n=n,
                address=address
            ) for address, n
            in zip(
                additional_addresses,
                range(
                    3 + len(additional_names),
                    3 + len(additional_names) + len(additional_addresses)
                )
            )
        ])
        additional_entries = '\n'.join([
            additional_dns_entries,
            additional_address_entries
        ])
        yield Effect(ReplaceStringInFile(
            path=config_path,
            placeholder='# additional names',
            entry_string=additional_entries,
        ))

    csr_path = os.path.join(outpath, 'csr.pem')

    yield Effect(GenerateCSR(
        output_path=csr_path,
        config_path=config_path,
        common_name=common_name,
        key_path=key_path
    ))

    cert_path = os.path.join(outpath, 'crt.pem')

    return Effect(SignCertificate(
        csr_path=csr_path,
        ca_cert_path=os.path.join(ca_path, 'ca-crt.pem'),
        ca_key_path=os.path.join(ca_path, 'ca-key.pem'),
        output_path=cert_path,
        config_path=config_path
    ))


def configs_path():
    this_dir, this_filename = os.path.split(__file__)
    return os.path.join(this_dir, "configs")


def generate_ca_command(args):
    sync_perform(
        dispatcher(),
        generate_ca(
            output_path=args.output,
            common_name=args.common_name,
            dry_run=args.dry_run,
        )
    )


def generate_cert_command(args):
    sync_perform(
        dispatcher(),
        generate_cert(
            dry_run=args.dry_run,
            ca_path=args.ca_path,
            outpath=args.output,
            common_name=args.common_name,
            kind=args.kind,
            additional_addresses=args.additional_address,
            additional_names=args.additional_name,
        )
    )


def print_usage(parser):
    def catch_args(*args, **kwargs):
        parser.print_help()
    return catch_args


argument_parser = argparse.ArgumentParser(
    description='Generate TLS certificates with openssl'
)
subparsers = argument_parser.add_subparsers()
argument_parser.set_defaults(func=print_usage(argument_parser))
argument_parser.add_argument(
    '--dry-run',
    help='Only print what would otherwise be excuted',
    dest='dry_run',
    action='store_true',
)


ca_parser = subparsers.add_parser('ca')
ca_parser.set_defaults(func=generate_ca_command)
ca_parser.add_argument(
    'output',
    type=str,
    help='The folder in which to store the CA'
)
ca_parser.add_argument(
    '--common-name',
    help='Common name of the certificate authority',
    type=str,
    dest='common_name'
)


cert_parser = subparsers.add_parser('cert')
cert_parser.set_defaults(func=generate_cert_command)
cert_parser.add_argument(
    '--kind',
    choices=['server', 'client'],
    required=True,
)
cert_parser.add_argument(
    'output',
    type=str,
    help='File basename of the generated certificate'
)
cert_parser.add_argument(
    '--ca-path',
    type=str,
    help='Path to the certificate authority we will sign the certificate with',
    required=True
)
cert_parser.add_argument(
    '--common-name',
    type=str,
    help='The common name of the host the certificate is for',
    required=True
)
cert_parser.add_argument(
    '--additional-address',
    type=str,
    help='Address of the machine, can be specified multiple times',
    action='append',
    default=[],
    required=False,
)
cert_parser.add_argument(
    '--additional-name',
    type=str,
    help='Name under which the can be reached, '
    'can be specified multiple times',
    action='append',
    default=[],
    required=False
)


def main():
    args = argument_parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
