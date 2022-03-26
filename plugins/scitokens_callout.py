#!/usr/bin/python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
import sys
import tempfile
import time

from glideinwms.lib import subprocessSupport, token_util

# This is a generic implementation of the the Scitoken plugin interface.
# VOs would implement their own version of this to interact with the
# token issuer for that VO.
#
# Dependencies are the python3-scitokens package, and a copy of the
# scitoken key.
#
# The key details are hardcoded below. At the minimum, key_file,
# key_id, and issuer need to be changed to the VO specific ones.


def get_credential(logger, group, entry, trust_domain):
    """
    Generates a credential given the parameters. This is called once
    per group, per entry. It is a good idea for the VO to do some
    caching here so that new tokens are only generated when required.
    """

    key_file = "/etc/condor/scitokens.pem"
    key_id = "1234"
    issuer = "https://scitokens.org/osg-connect"
    scope = "compute.read compute.modify compute.create compute.cancel"
    wlcg_ver = "1.0"
    tkn_max_lifetime = 3600
    tkn_file = ""
    tkn_str = ""
    tkn_lifetime = tkn_max_lifetime
    tmpnm = ""

    audience = None
    if "gatekeeper" in entry:
        audience = entry["gatekeeper"].split()[-1]
    subject = None
    if "name" in entry:
        subject = "vofrontend-%s" % (entry["name"])

    tkn_dir = "/var/lib/gwms-frontend/tokens.d"
    if not os.path.exists(tkn_dir):
        os.mkdir(tkn_dir, 0o700)
    tkn_file = os.path.join(tkn_dir, group + "." + entry["name"] + ".scitoken")

    try:
        # only generate a new token if the file is expired
        tkn_age = sys.maxsize
        if os.path.exists(tkn_file):
            # we are short cutting the the calculation of the life time - the
            # file modification age is the same as the token age
            tkn_age = time.time() - os.stat(tkn_file).st_mtime
        if tkn_age > tkn_max_lifetime - 600:  # renew slightly before token expires
            (fd, tmpnm) = tempfile.mkstemp()
            cmd = (
                f"/usr/bin/scitokens-admin-create-token"
                f" --keyfile {key_file}"
                f" --key_id {key_id}"
                f" --issuer {issuer}"
                f" --lifetime {tkn_max_lifetime}"
                f' sub="{subject}"'
                f' aud="{audience}"'
                f' scope="{scope}"'
                f' wlcg.ver="{wlcg_ver}"'
            )
            tkn_str = subprocessSupport.iexe_cmd(cmd)
            os.write(fd, tkn_str.encode("utf-8"))
            os.close(fd)
            shutil.move(tmpnm, tkn_file)
            os.chmod(tkn_file, 0o600)
            logger.debug("created token %s" % tkn_file)
        elif os.path.exists(tkn_file):
            with open(tkn_file) as fbuf:
                for line in fbuf:
                    tkn_str += line
            tkn_str = tkn_str.strip()
            tkn_lifetime = tkn_max_lifetime - tkn_age
    except Exception as err:
        logger.warning("failed to create %s" % tkn_file)
    finally:
        if os.path.exists(tmpnm):
            os.remove(tmpnm)

    return tkn_str, tkn_lifetime
