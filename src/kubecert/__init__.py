#!/usr/bin/env python3

import argparse
import os
import os.path
import subprocess


def configs_path():
    this_dir, this_filename = os.path.split(__file__)
    return os.path.join(this_dir, "configs")


def make_command_runner(dry_run):
    def run(cmd, stdin=None, stdout=None):
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
    return run


def generate_ca(args):
    run_cmd = make_command_runner(args.dry_run)
    outpath = args.output
    run_cmd("mkdir -vp {out}".format(out=outpath))
    run_cmd("openssl genrsa -out {out} 2048".format(
        out=outpath + "/ca-key.pem"
    ))
    run_cmd('openssl req -x509 -new -nodes -key {key} -days 10000 -out {out} -subj "/CN={cn}"'.format(
        key=outpath + "/ca-key.pem",
        out=outpath + "/ca-crt.pem",
        cn=args.common_name
    ))


def _generate_cert(args):
    generate_cert(
        dry_run=args.dry_run,
        ca_path=args.ca_path,
        outname=args.output,
        common_name=args.common_name,
        kind=args.kind,
        server_ip=args.server_ip,
    )


def generate_cert(dry_run, ca_path, outname, common_name, kind, server_ip=None):
    run_cmd = make_command_runner(dry_run)

    # generate certificate key
    run_cmd('mkdir -vp {path}'.format(
        path=ca_path + "/certs"
    ))
    run_cmd('openssl genrsa -out {outpath} 2048'.format(
        outpath=ca_path + "/certs/" + outname + "-key.pem"
    ))

    if kind == 'client':
        conf_path = os.path.join(
            configs_path(), "client-openssl.conf"
        )
    else:
        conf_path = os.path.join(
            configs_path(), "server-openssl.conf"
        )

    # copy config file
    config_path = ca_path + "/certs/" + outname + "-openssl.conf"
    run_cmd('rm -f {config_path}'.format(
        config_path=config_path
    ))
    run_cmd('cp -v {conf_path} {out_path}'.format(
        conf_path=conf_path,
        out_path=config_path,
    ))

    # create csr
    run_cmd('openssl req -new -key {keypath} -out {outpath} -subj "/CN={common_name}" -config {config}'.format(
        keypath=ca_path + "/certs/" + outname + "-key.pem",
        outpath=ca_path + "/certs/" + outname + ".csr",
        common_name=common_name,
        config=config_path,
    ))
    if server_ip is not None:
        run_cmd('sed -i.bak "s/# additional names.*/IP.3 = {address}/" {config_path}'.format(
            address=server_ip,
            config_path=config_path,
        ))
        run_cmd('rm -fv {config_path}.bak'.format(
            config_path=config_path
        ))

    # sign certificate
    run_cmd('openssl x509 -req -in {csrpath} -CA {cacert} -CAkey {cakey} -CAcreateserial -out {outpath} -days 365 -extensions v3_req -extfile {confpath}'.format(
        csrpath=ca_path + "/certs/" + outname + ".csr",
        cacert=ca_path + "/ca-crt.pem",
        cakey=ca_path + "/ca-key.pem",
        outpath=ca_path + "/certs/" + outname + "-crt.pem",
        confpath=ca_path + "/certs/" + outname + "-openssl.conf",
    ))


def find_hosts_in_ansible_group(group, inventory_path):
    run_cmd = make_command_runner(dry_run=False)
    proc_input = 'cd {group}\ndebug msg="IP_ADDRESS={{{{ ansible_ssh_host }}}}"'.format(
        group=group,
    )
    if inventory_path is None:
        ansible_console_cmd = 'ansible-console'
    else:
        ansible_console_cmd = (
            'ansible-console -i {inventory_path}'.format(
                inventory_path=inventory_path,
            ))
    proc_out = run_cmd(
        ansible_console_cmd,
        stdin=proc_input,
        stdout=subprocess.PIPE,
    )
    output = proc_out[0].splitlines()
    addresses = [
        line.split('=')[-1][:-1] for line
        in output
        if 'IP_ADDRESS' in line
    ]
    return addresses


def concat(xs):
    ret = []
    for x in xs:
        ret += x
    return ret


def generate_group_certs(args):
    ca_path = args.ca_path
    groups_str = args.groups
    ansible_inventory = args.ansible_inventory
    groups = groups_str.split(',')

    # find out hosts to issue certificate for
    hosts = concat([
        find_hosts_in_ansible_group(group, ansible_inventory)
        for group in groups
    ])

    # issue certificates
    for host in hosts:
        generate_cert(
            dry_run=args.dry_run,
            ca_path=ca_path,
            outname=host.replace('.','-'),
            common_name=host,
            kind="server",
            server_ip=host,
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
ca_parser.set_defaults(func=generate_ca)
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
cert_parser.set_defaults(func=_generate_cert)
cert_parser.add_argument(
    '--kind',
    choices=[ 'server', 'client' ],
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
    '--server-ip',
    type=str,
    help='The IP address of the target machine',
    default=None,
    required=False,
)

kube_certs_parser = subparsers.add_parser('group-certs')
kube_certs_parser.set_defaults(func=generate_group_certs)
kube_certs_parser.add_argument(
    '--ca-path',
    type=str,
    help='Path to the certificate authority that is used to sign the generated certs',
    required=True,
)
kube_certs_parser.add_argument(
    '--groups',
    type=str,
    help='Comma seperated list of ansible groups that are part of the cluster',
    required=True,
)
kube_certs_parser.add_argument(
    '--ansible-inventory',
    type=str,
    help='Ansible inventory path',
    required=False,
)


def main():
    args = argument_parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
