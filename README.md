# custodia.ipa — IPA vault plugin for Custodia

**WARNING** *custodia.ipa is a tech preview with a provisional API.*

custodia.ipa is a storage plugin for
[Custodia](https://custodia.readthedocs.io/). It provides integration with
[FreeIPA](http://www.freeipa.org)'s
[vault](https://www.freeipa.org/page/V4/Password_Vault) facility. Secrets are
encrypted and stored in [Dogtag](http://www.dogtagpki.org)'s Key Recovery
Agent. 
 

## Requirements

### Installation

* pip
* setuptools >= 18.0

### Runtime

* custodia >= 0.3.1
* ipalib >= 4.5.0
* ipaclient >= 4.5.0
* Python 2.7 (Python 3 support in IPA vault is unstable.)

custodia.ipa requires an IPA-enrolled host and a Kerberos TGT for
authentication. It is recommended to provide credentials with a keytab file or
GSS-Proxy.

### Testing and development

* wheel
* tox

### virtualenv requirements

custodia.ipa depends on several binary extensions and shared libraries for
e.g. python-cryptography, python-gssapi, python-ldap, and python-nss. For
installation in a virtual environment, a C compiler and several development
packages are required.

```
$ virtualenv venv
$ venv/bin/pip install --upgrade custodia.ipa
```

#### Fedora

```
$ sudo dnf install python2 python-pip python-virtualenv python-devel \
    gcc redhat-rpm-config krb5-workstation krb5-devel libffi-devel \
    nss-devel openldap-devel cyrus-sasl-devel openssl-devel
```

#### Debian / Ubuntu

```
$ sudo apt-get update
$ sudo apt-get install -y python2.7 python-pip python-virtualenv python-dev \
    gcc krb5-user libkrb5-dev libffi-dev libnss3-dev libldap2-dev \
    libsasl2-dev libssl-dev
```

---

## Example configuration

Create directories

```
$ sudo mkdir /etc/custodia /var/lib/custodia /var/log/custodia /var/run/custodia
$ sudo chown USER:GROUP /var/lib/custodia /var/log/custodia /var/run/custodia
$ sudo chmod 750 /var/lib/custodia /var/log/custodia
```

Create service account and keytab

```
$ kinit admin
$ ipa service-add custodia/client1.ipa.example
$ ipa service-allow-create-keytab custodia/client1.ipa.example --users=admin
$ mkdir -p /etc/custodia
$ ipa-getkeytab -p custodia/client1.ipa.example -k /etc/custodia/custodia.keytab
```

Create ```/etc/custodia/custodia.conf```

```
[DEFAULT]
confdir = /etc/custodia
libdir = /var/lib/custodia
logdir = /var/log/custodia
rundir = /var/run/custodia

[global]
debug = true
server_socket = ${rundir}/custodia.sock
auditlog = ${logdir}/audit.log

[store:vault]
handler = IPAVault
keytab = {confdir}/custodia.keytab
ccache = FILE:{rundir}/ccache

[auth:creds]
handler = SimpleCredsAuth
uid = root
gid = root

[authz:paths]
handler = SimplePathAuthz
paths = /. /secrets

[/]
handler = Root

[/secrets]
handler = Secrets
store = vault
```

Run Custodia server

```
$ custodia /etc/custodia/custodia.conf
```