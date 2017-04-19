# Copyright (C) 2016  Custodia Project Contributors - see LICENSE file
"""FreeIPA vault store (PoC)
"""
from __future__ import absolute_import

from ipalib.errors import DuplicateEntry, NotFound

import six

from custodia.plugin import CSStore, CSStoreError, CSStoreExists, PluginOption
from .interface import IPAInterface


def krb5_unparse_principal_name(name):
    """Split a Kerberos principal name into parts

    Returns:
       * ('host', hostname, realm) for a host principal
       * (servicename, hostname, realm) for a service principal
       * (None, username, realm) for a user principal

    :param text name: Kerberos principal name
    :return: (service, host, realm) or (None, username, realm)
    """
    prefix, realm = name.split(u'@')
    if u'/' in prefix:
        service, host = prefix.rsplit(u'/', 1)
        return service, host, realm
    else:
        return None, prefix, realm


class IPAVault(CSStore):
    # vault arguments
    principal = PluginOption(
        str, None,
        "Service principal for service vault (auto-discovered from GSSAPI)"
    )
    user = PluginOption(
        str, None,
        "User name for user vault (auto-discovered from GSSAPI)"
    )
    vault_type = PluginOption(
        str, None,
        "vault type, one of 'user', 'service', 'shared', or "
        "auto-discovered from GSSAPI"
    )

    def __init__(self, config, section=None):
        super(IPAVault, self).__init__(config, section)
        self.ipa = IPAInterface.get_instance()
        # connect
        with self.ipa:
            # retrieve and cache KRA transport cert
            response = self.ipa.Command.vaultconfig_show()
            servers = response[u'result'][u'kra_server_server']
            self.logger.info("KRA server(s) %s", ', '.join(servers))

        service, user_host, realm = krb5_unparse_principal_name(
            self.ipa.principal)
        self._init_vault_args(service, user_host, realm)

    def _init_vault_args(self, service, user_host, realm):
        if self.vault_type is None:
            self.vault_type = 'user' if service is None else 'service'
            self.logger.info("Setting vault type to '%s' from Kerberos",
                             self.vault_type)

        if self.vault_type == 'shared':
            self._vault_args = {'shared': True}
        elif self.vault_type == 'user':
            if self.user is None:
                if service is not None:
                    msg = "{!r}: User vault requires 'user' parameter"
                    raise ValueError(msg.format(self))
                else:
                    self.user = user_host
                    self.logger.info(u"Setting username '%s' from Kerberos",
                                     self.user)
            if six.PY2 and isinstance(self.user, str):
                self.user = self.user.decode('utf-8')
            self._vault_args = {'username': self.user}
        elif self.vault_type == 'service':
            if self.principal is None:
                if service is None:
                    msg = "{!r}: Service vault requires 'principal' parameter"
                    raise ValueError(msg.format(self))
                else:
                    self.principal = u'/'.join((service, user_host))
                    self.logger.info(u"Setting principal '%s' from Kerberos",
                                     self.principal)
            if six.PY2 and isinstance(self.principal, str):
                self.principal = self.principal.decode('utf-8')
            self._vault_args = {'service': self.principal}
        else:
            msg = '{!r}: Invalid vault type {}'
            raise ValueError(msg.format(self, self.vault_type))

    def _mangle_key(self, key):
        if '__' in key:
            raise ValueError
        key = key.replace('/', '__')
        if isinstance(key, bytes):
            key = key.decode('utf-8')
        return key

    def get(self, key):
        key = self._mangle_key(key)
        with self.ipa as ipa:
            try:
                result = ipa.Command.vault_retrieve(
                    key, **self._vault_args)
            except NotFound as e:
                self.logger.info(str(e))
                return None
            except Exception:
                msg = "Failed to retrieve entry {}".format(key)
                self.logger.exception(msg)
                raise CSStoreError(msg)
            else:
                return result[u'result'][u'data']

    def set(self, key, value, replace=False):
        key = self._mangle_key(key)
        if not isinstance(value, bytes):
            value = value.encode('utf-8')
        with self.ipa as ipa:
            try:
                ipa.Command.vault_add(
                    key, ipavaulttype=u"standard", **self._vault_args)
            except DuplicateEntry:
                if not replace:
                    raise CSStoreExists(key)
            except Exception:
                msg = "Failed to add entry {}".format(key)
                self.logger.exception(msg)
                raise CSStoreError(msg)
            try:
                ipa.Command.vault_archive(
                    key, data=value, **self._vault_args)
            except Exception:
                msg = "Failed to archive entry {}".format(key)
                self.logger.exception(msg)
                raise CSStoreError(msg)

    def span(self, key):
        raise CSStoreError("span is not implemented")

    def list(self, keyfilter=None):
        with self.ipa as ipa:
            try:
                result = ipa.Command.vault_find(
                    ipavaulttype=u"standard", **self._vault_args)
            except Exception:
                msg = "Failed to list entries"
                self.logger.exception(msg)
                raise CSStoreError(msg)

        names = []
        for entry in result[u'result']:
            cn = entry[u'cn'][0]
            key = cn.replace('__', '/')
            if keyfilter is not None and not key.startswith(keyfilter):
                continue
            names.append(key.rsplit('/', 1)[-1])
        return names

    def cut(self, key):
        key = self._mangle_key(key)
        with self.ipa as ipa:
            try:
                ipa.Command.vault_del(key, **self._vault_args)
            except NotFound:
                return False
            except Exception:
                msg = "Failed to delete entry {}".format(key)
                self.logger.exception(msg)
                raise CSStoreError(msg)
            else:
                return True


if __name__ == '__main__':
    from custodia.compat import configparser
    from custodia.log import setup_logging

    parser = configparser.ConfigParser(
        interpolation=configparser.ExtendedInterpolation()
    )
    parser.read_string(u"""
    [auth:ipa]
    handler = IPAInterface
    [store:ipa_vault]
    handler = IPAVault
    """)

    setup_logging(debug=True, auditfile=None)
    IPAInterface(parser, 'auth:ipa')
    v = IPAVault(parser, 'store:ipa_vault')
    v.set('foo', 'bar', replace=True)
    print(v.get('foo'))
    print(v.list())
    v.cut('foo')
    print(v.list())
