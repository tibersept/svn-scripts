#!/usr/bin/env python

import os
import shutil
import sys, getopt

DEFAULT_OPENSSL_FILE = '/etc/pki/tls/openssl.cnf'
BEGIN_TLS_V1_SECTION = '# <begin_tls_v1_activation>'
END_TLS_V1_SECTION = '# <end_tls_v1_activation>'
INSERT_MAIN_REFERENCE_AT = '# Extra OBJECT IDENTIFIER info:'

def read_contents(ssl_conf_file):
    with open(ssl_conf_file, 'r') as fin:
        contents = fin.readlines()
    return contents

def write_contents(ssl_conf_file, contents):
    with open(ssl_conf_file, 'w') as fout:
        contents = ''.join(contents)
        fout.write(contents)

def has_backup(ssl_conf_file):
    return os.path.isfile(ssl_conf_file+'.backup')

def create_backup(ssl_conf_file):
    return shutil.copyfile(ssl_conf_file, (ssl_conf_file + '.backup'))

def has_enabled_tls(contents):
    for line in contents:
        if line.startswith(BEGIN_TLS_V1_SECTION):
            return True
    return False

def find_main_reference_insert_position(contents):
    for line_index in range(len(contents)):
        line = contents[line_index]
        if (line.startswith(INSERT_MAIN_REFERENCE_AT)):
            return line_index
    return len(contents)

def insert_main_reference(contents, index):
    contents.insert(index, BEGIN_TLS_V1_SECTION)
    contents.insert(index+1, '\nopenssl_conf = default_conf\n')
    contents.insert(index+2, END_TLS_V1_SECTION)
    contents.insert(index+3, '\n')

def insert_tls_v1_configuration(contents):
    contents.append(BEGIN_TLS_V1_SECTION)
    contents.append('\n[ default_conf ]\n')
    contents.append('ssl_conf = ssl_sect\n')
    contents.append('[ ssl_sect ]\n')
    contents.append('system_default = ssl_default_sect\n')
    contents.append('[ ssl_default_sect ]\n')
    contents.append('MinProtocol = TLSv1\n')
    contents.append('CipherString = DEFAULT:@SECLEVEL=1\n')
    contents.append(END_TLS_V1_SECTION)
    contents.append('\n')

def remove_tls_v1_configuration(contents):
    clean_contents = []
    filter_content = False
    for line in contents:
        if line.startswith(BEGIN_TLS_V1_SECTION):
            filter_content = True
        if not filter_content:
            clean_contents.append(line)
        if line.startswith(END_TLS_V1_SECTION):
            filter_content = False
    return clean_contents 

def enable_tls_v1(ssl_conf_file):
    contents = read_contents(ssl_conf_file)
    if has_enabled_tls(contents):
        print 'This file already has TLS v1 modifications!'
        return False
    insertion_index = find_main_reference_insert_position(contents)
    insert_main_reference(contents, insertion_index)
    insert_tls_v1_configuration(contents)
    write_contents(ssl_conf_file, contents)
    return True

def disable_tls_v1(ssl_conf_file):
    contents = read_contents(ssl_conf_file)
    if not has_enabled_tls(contents):
        print 'This file has no TLS v1 modifications!'
        return False
    contents = remove_tls_v1_configuration(contents)
    write_contents(ssl_conf_file, contents)
    return True

def print_ssl_conf(ssl_conf_file):
    with open(ssl_conf_file, 'r') as fin:
        print(fin.read())

def check_tls_v1(ssl_conf_file):
    contents = read_contents(ssl_conf_file)
    return has_enabled_tls(contents)

def main(argv):
    openssl_file = DEFAULT_OPENSSL_FILE
    option_enable_tls_v1 = True
    option_check_tls_v1_support = False
    verbose = False
    try:
        opts, args = getopt.getopt(argv, 'hvc:s:', ['config=','state='])
    except getopt.GetoptError:
        print 'support_tls_v1.py [-c /path/to/openssl.cnf] [-s on|off|check]'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'support_tls_v1.py [-c /path/to/openssl.cnf] [-s on|off|check]'
            sys.exit()
        elif opt == '-v':
            verbose = True
        elif opt in ('-c', '--config'):
            openssl_file = arg
        elif opt in ('-s', '--state'):
            if (arg.lower() == 'check'):
                option_check_tls_v1_support = True
                option_enable_tls_v1 = False
            else:
                option_enable_tls_v1 = (arg.lower() == 'on')
            
    print ('OpenSSL Config file ' + openssl_file)

    if option_check_tls_v1_support:
        print ('Support for TLSv1 is ' + ('enabled' if check_tls_v1(openssl_file) else 'disabled'))
    else:
        print ('TLS v1 will be ' + ('enabled' if option_enable_tls_v1 else 'disabled'))

        if not has_backup(openssl_file):
            create_backup(openssl_file)
            print ('Backup file '+(openssl_file+'.backup')+' was created.')
        print ('... ... ...')
        success = enable_tls_v1(openssl_file) if option_enable_tls_v1 else disable_tls_v1(openssl_file)
        print ('TLS v1 was ' + ('NOT ' if (not success) else '') + ('enabled' if option_enable_tls_v1 else 'disabled'))
        if verbose and success:
            print '\n\n Your new OpenSSL Configuration: \n'
            print_ssl_conf(openssl_file)
    
    
if __name__ == '__main__':
    # execute only if run as a script
    main(sys.argv[1:])

