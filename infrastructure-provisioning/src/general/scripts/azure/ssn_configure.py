#!/usr/bin/python3

# *****************************************************************************
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# ******************************************************************************

import datalab.fab
import datalab.actions_lib
import datalab.meta_lib
import json
import logging
import os
import sys
import traceback
import subprocess
from fabric import *

if __name__ == "__main__":
    local_log_filename = "{}_{}.log".format(os.environ['conf_resource'], os.environ['request_id'])
    local_log_filepath = "/logs/" + os.environ['conf_resource'] + "/" + local_log_filename
    logging.basicConfig(format='%(levelname)-8s [%(asctime)s]  %(message)s',
                        level=logging.DEBUG,
                        filename=local_log_filepath)

    def clear_resources():
        AzureActions.remove_instance(ssn_conf['resource_group_name'], ssn_conf['instance_name'])
        for datalake in AzureMeta.list_datalakes(ssn_conf['resource_group_name']):
            if ssn_conf['datalake_store_name'] == datalake.tags["Name"]:
                AzureActions.delete_datalake_store(ssn_conf['resource_group_name'], datalake.name)
        if 'azure_security_group_name' not in os.environ:
            AzureActions.remove_security_group(ssn_conf['resource_group_name'], ssn_conf['security_group_name'])
        if 'azure_subnet_name' not in os.environ:
            AzureActions.remove_subnet(ssn_conf['resource_group_name'], ssn_conf['vpc_name'],
                                       ssn_conf['subnet_name'])
        if 'azure_vpc_name' not in os.environ:
            AzureActions.remove_vpc(ssn_conf['resource_group_name'], ssn_conf['vpc_name'])
        if 'azure_resource_group_name' not in os.environ:
            AzureActions.remove_resource_group(ssn_conf['resource_group_name'], ssn_conf['region'])


    try:
        AzureMeta = datalab.meta_lib.AzureMeta()
        AzureActions = datalab.actions_lib.AzureActions()
        ssn_conf = dict()
        ssn_conf['instance'] = 'ssn'

        logging.info('[DERIVING NAMES]')
        print('[DERIVING NAMES]')

        ssn_conf['billing_enabled'] = True
        # We need to cut service_base_name to 20 symbols do to the Azure Name length limitation
        ssn_conf['service_base_name'] = os.environ['conf_service_base_name'] = datalab.fab.replace_multi_symbols(
            os.environ['conf_service_base_name'][:20], '-', True)
        # Check azure predefined resources
        ssn_conf['resource_group_name'] = os.environ.get('azure_resource_group_name',
                                                         '{}-resource-group'.format(ssn_conf['service_base_name']))
        ssn_conf['vpc_name'] = os.environ.get('azure_vpc_name', '{}-vpc'.format(ssn_conf['service_base_name']))
        ssn_conf['subnet_name'] = os.environ.get('azure_subnet_name', '{}-subnet'.format(ssn_conf['service_base_name']))
        ssn_conf['security_group_name'] = os.environ.get('azure_security_group_name', '{}-sg'.format(
            ssn_conf['service_base_name']))
        # Default variables
        ssn_conf['region'] = os.environ['azure_region']
        ssn_conf['default_endpoint_name'] = os.environ['default_endpoint_name']
        ssn_conf['datalake_store_name'] = '{}-ssn-datalake'.format(ssn_conf['service_base_name'])
        ssn_conf['datalake_shared_directory_name'] = '{}-shared-folder'.format(ssn_conf['service_base_name'])
        ssn_conf['instance_name'] = '{}-ssn'.format(ssn_conf['service_base_name'])
        ssn_conf['ssh_key_path'] = '{}{}.pem'.format(os.environ['conf_key_dir'], os.environ['conf_key_name'])
        ssn_conf['datalab_ssh_user'] = os.environ['conf_os_user']
        ssn_conf['instance_dns_name'] = 'host-{}.{}.cloudapp.azure.com'.format(ssn_conf['instance_name'],
                                                                               ssn_conf['region'])
        if os.environ['conf_network_type'] == 'private':
            ssn_conf['instnace_ip'] = AzureMeta.get_private_ip_address(ssn_conf['resource_group_name'],
                                                                       ssn_conf['instance_name'])
            ssn_conf['instance_host'] = ssn_conf['instnace_ip']
        else:
            ssn_conf['instnace_ip'] = AzureMeta.get_instance_public_ip_address(ssn_conf['resource_group_name'],
                                                                               ssn_conf['instance_name'])
            ssn_conf['instance_host'] = ssn_conf['instance_dns_name']

        if os.environ['conf_stepcerts_enabled'] == 'true':
            ssn_conf['step_cert_sans'] = ' --san {0} '.format(AzureMeta.get_private_ip_address(
                ssn_conf['resource_group_name'], ssn_conf['instance_name']))
            if os.environ['conf_network_type'] == 'public':
                ssn_conf['step_cert_sans'] += ' --san {0} --san {1} '.format(
                    AzureMeta.get_instance_public_ip_address(ssn_conf['resource_group_name'],
                                                             ssn_conf['instance_name']),
                    ssn_conf['instance_dns_name'])
        else:
            ssn_conf['step_cert_sans'] = ''

        try:
            if os.environ['azure_offer_number'] == '':
                raise KeyError
            if os.environ['azure_currency'] == '':
                raise KeyError
            if os.environ['azure_locale'] == '':
                raise KeyError
            if os.environ['azure_region_info'] == '':
                raise KeyError
        except KeyError:
            ssn_conf['billing_enabled'] = False
        if not ssn_conf['billing_enabled']:
            os.environ['azure_offer_number'] = 'None'
            os.environ['azure_currency'] = 'None'
            os.environ['azure_locale'] = 'None'
            os.environ['azure_region_info'] = 'None'
        if os.environ['conf_os_family'] == 'debian':
            ssn_conf['initial_user'] = 'ubuntu'
            ssn_conf['sudo_group'] = 'sudo'
        if os.environ['conf_os_family'] == 'redhat':
            ssn_conf['initial_user'] = 'ec2-user'
            ssn_conf['sudo_group'] = 'wheel'
    except Exception as err:
        datalab.fab.append_result("Failed to generate variables dictionary.", str(err))
        clear_resources()
        sys.exit(1)

    try:
        logging.info('[CREATING DATALAB SSH USER]')
        print('[CREATING DATALAB SSH USER]')
        params = "--hostname {} --keyfile {} --initial_user {} --os_user {} --sudo_group {}".format \
            (ssn_conf['instance_host'], ssn_conf['ssh_key_path'], ssn_conf['initial_user'],
             ssn_conf['datalab_ssh_user'],
             ssn_conf['sudo_group'])
        subprocess.run("~/scripts/{}.py {}".format('create_ssh_user', params), shell=True, check=True)
    except Exception as err:
        traceback.print_exc()
        clear_resources()
        datalab.fab.append_result("Failed creating ssh user 'datalab-user'.", str(err))
        sys.exit(1)

    try:
        logging.info('[INSTALLING PREREQUISITES TO SSN INSTANCE]')
        print('[INSTALLING PREREQUISITES TO SSN INSTANCE]')
        params = "--hostname {} --keyfile {} --pip_packages 'backoff bcrypt==3.1.7 argparse fabric==1.14.0 pymongo pyyaml " \
                 "pycryptodome azure==2.0.0' --user {} --region {}".format(ssn_conf['instance_host'],
                                                                       ssn_conf['ssh_key_path'],
                                                                       ssn_conf['datalab_ssh_user'],
                                                                       ssn_conf['region'])
        subprocess.run("~/scripts/{}.py {}".format('install_prerequisites', params), shell=True, check=True)
    except Exception as err:
        traceback.print_exc()
        clear_resources()
        datalab.fab.append_result("Failed installing software: pip, packages.", str(err))
        sys.exit(1)

    try:
        logging.info('[CONFIGURE SSN INSTANCE]')
        print('[CONFIGURE SSN INSTANCE]')
        additional_config = {"nginx_template_dir": "/root/templates/",
                             "service_base_name": ssn_conf['service_base_name'],
                             "security_group_id": ssn_conf['security_group_name'], "vpc_id": ssn_conf['vpc_name'],
                             "subnet_id": ssn_conf['subnet_name'], "admin_key": os.environ['conf_key_name']}
        params = "--hostname {} --keyfile {} --additional_config '{}' --os_user {} --datalab_path {} " \
                 "--tag_resource_id {} --step_cert_sans '{}'". \
            format(ssn_conf['instance_host'], ssn_conf['ssh_key_path'], json.dumps(additional_config),
                   ssn_conf['datalab_ssh_user'], os.environ['ssn_datalab_path'], ssn_conf['service_base_name'],
                   ssn_conf['step_cert_sans'])
        subprocess.run("~/scripts/{}.py {}".format('configure_ssn_node', params), shell=True, check=True)
    except Exception as err:
        traceback.print_exc()
        clear_resources()
        datalab.fab.append_result("Failed configuring ssn.", str(err))
        sys.exit(1)

    try:
        logging.info('[CONFIGURING DOCKER AT SSN INSTANCE]')
        print('[CONFIGURING DOCKER AT SSN INSTANCE]')
        additional_config = [{"name": "base", "tag": "latest"},
                             {"name": "edge", "tag": "latest"},
                             {"name": "project", "tag": "latest"},
                             {"name": "jupyter", "tag": "latest"},
                             {"name": "jupyterlab", "tag": "latest"},
                             {"name": "rstudio", "tag": "latest"},
                             {"name": "zeppelin", "tag": "latest"},
                             {"name": "tensor", "tag": "latest"},
                             {"name": "deeplearning", "tag": "latest"},
                             {"name": "dataengine", "tag": "latest"}]
        params = "--hostname {} --keyfile {} --additional_config '{}' --os_family {} --os_user {} --datalab_path {} " \
                 "--cloud_provider {} --region {}".format(ssn_conf['instance_host'], ssn_conf['ssh_key_path'],
                                                          json.dumps(additional_config), os.environ['conf_os_family'],
                                                          ssn_conf['datalab_ssh_user'], os.environ['ssn_datalab_path'],
                                                          os.environ['conf_cloud_provider'], ssn_conf['region'])
        subprocess.run("~/scripts/{}.py {}".format('configure_docker', params), shell=True, check=True)
    except Exception as err:
        traceback.print_exc()
        clear_resources()
        datalab.fab.append_result("Unable to configure docker.", str(err))
        sys.exit(1)

    try:
        logging.info('[CONFIGURE SSN INSTANCE UI]')
        print('[CONFIGURE SSN INSTANCE UI]')
        ssn_conf['azure_auth_path'] = '/home/{}/keys/azure_auth.json'.format(ssn_conf['datalab_ssh_user'])
        ssn_conf['ldap_login'] = 'false'

        cloud_params = [
            {
                'key': 'KEYCLOAK_REDIRECT_URI',
                'value': "https://{0}/".format(ssn_conf['instance_host'])
            },
            {
                'key': 'KEYCLOAK_REALM_NAME',
                'value': os.environ['keycloak_realm_name']
            },
            {
                'key': 'KEYCLOAK_AUTH_SERVER_URL',
                'value': os.environ['keycloak_auth_server_url']
            },
            {
                'key': 'KEYCLOAK_CLIENT_NAME',
                'value': os.environ['keycloak_client_name']
            },
            {
                'key': 'KEYCLOAK_CLIENT_SECRET',
                'value': os.environ['keycloak_client_secret']
            },
            {
                'key': 'KEYCLOAK_USER_NAME',
                'value': os.environ['keycloak_user']
            },
            {
                'key': 'KEYCLOAK_PASSWORD',
                'value': os.environ['keycloak_user_password']
            },
            {
                'key': 'CONF_OS',
                'value': os.environ['conf_os_family']
            },
            {
                'key': 'SERVICE_BASE_NAME',
                'value': ssn_conf['service_base_name']
            },
            {
                'key': 'EDGE_INSTANCE_SIZE',
                'value': os.environ['azure_edge_instance_size']
            },
            {
                'key': 'SUBNET_ID',
                'value': ssn_conf['subnet_name']
            },
            {
                'key': 'REGION',
                'value': ssn_conf['region']
            },
            {
                'key': 'ZONE',
                'value': ''
            },
            {
                'key': 'TAG_RESOURCE_ID',
                'value': ''
            },
            {
                'key': 'SG_IDS',
                'value': ssn_conf['security_group_name']
            },
            {
                'key': 'SSN_INSTANCE_SIZE',
                'value': os.environ['azure_ssn_instance_size']
            },
            {
                'key': 'VPC_ID',
                'value': ssn_conf['vpc_name']
            },
            {
                'key': 'CONF_KEY_DIR',
                'value': os.environ['conf_key_dir']
            },
            {
                'key': 'LDAP_HOST',
                'value': os.environ['ldap_hostname']
            },
            {
                'key': 'LDAP_DN',
                'value': os.environ['ldap_dn']
            },
            {
                'key': 'LDAP_OU',
                'value': os.environ['ldap_ou']
            },
            {
                'key': 'LDAP_USER_NAME',
                'value': os.environ['ldap_service_username']
            },
            {
                'key': 'LDAP_USER_PASSWORD',
                'value': os.environ['ldap_service_password']
            },
            {
                'key': 'AZURE_RESOURCE_GROUP_NAME',
                'value': ssn_conf['resource_group_name']
            },
            {
                'key': 'GCP_PROJECT_ID',
                'value': ''
            },
            {
                'key': 'SUBNET2_ID',
                'value': ''
            },
            {
                'key': 'VPC2_ID',
                'value': ''
            },
            {
                'key': 'PEERING_ID',
                'value': ''
            },
            {
                'key': 'CONF_IMAGE_ENABLED',
                'value': os.environ['conf_image_enabled']
            },
            {
                'key': "AZURE_AUTH_FILE_PATH",
                'value': ssn_conf['azure_auth_path']
            }
        ]

        if os.environ['conf_stepcerts_enabled'] == 'true':
            cloud_params.append(
                {
                    'key': 'STEP_CERTS_ENABLED',
                    'value': os.environ['conf_stepcerts_enabled']
                })
            cloud_params.append(
                {
                    'key': 'STEP_ROOT_CA',
                    'value': os.environ['conf_stepcerts_root_ca']
                })
            cloud_params.append(
                {
                    'key': 'STEP_KID_ID',
                    'value': os.environ['conf_stepcerts_kid']
                })
            cloud_params.append(
                {
                    'key': 'STEP_KID_PASSWORD',
                    'value': os.environ['conf_stepcerts_kid_password']
                })
            cloud_params.append(
                {
                    'key': 'STEP_CA_URL',
                    'value': os.environ['conf_stepcerts_ca_url']
                })
            cloud_params.append(
                {
                    'key': 'LETS_ENCRYPT_ENABLED',
                    'value': 'false'
                })
            cloud_params.append(
                {
                    'key': 'LETS_ENCRYPT_DOMAIN_NAME',
                    'value': ''
                })
            cloud_params.append(
                {
                    'key': 'LETS_ENCRYPT_EMAIL',
                    'value': ''
                })
        elif os.environ['conf_letsencrypt_enabled'] == 'true':
            cloud_params.append(
                {
                    'key': 'LETS_ENCRYPT_ENABLED',
                    'value': os.environ['conf_letsencrypt_enabled']
                })
            cloud_params.append(
                {
                    'key': 'LETS_ENCRYPT_DOMAIN_NAME',
                    'value': os.environ['conf_letsencrypt_domain_name']
                })
            cloud_params.append(
                {
                    'key': 'LETS_ENCRYPT_EMAIL',
                    'value': os.environ['conf_letsencrypt_email']
                })
            cloud_params.append(
                {
                    'key': 'STEP_CERTS_ENABLED',
                    'value': 'false'
                })
            cloud_params.append(
                {
                    'key': 'STEP_ROOT_CA',
                    'value': ''
                })
            cloud_params.append(
                {
                    'key': 'STEP_KID_ID',
                    'value': ''
                })
            cloud_params.append(
                {
                    'key': 'STEP_KID_PASSWORD',
                    'value': ''
                })
            cloud_params.append(
                {
                    'key': 'STEP_CA_URL',
                    'value': ''
                })
        else:
            cloud_params.append(
                {
                    'key': 'STEP_CERTS_ENABLED',
                    'value': 'false'
                })
            cloud_params.append(
                {
                    'key': 'STEP_ROOT_CA',
                    'value': ''
                })
            cloud_params.append(
                {
                    'key': 'STEP_KID_ID',
                    'value': ''
                })
            cloud_params.append(
                {
                    'key': 'STEP_KID_PASSWORD',
                    'value': ''
                })
            cloud_params.append(
                {
                    'key': 'STEP_CA_URL',
                    'value': ''
                })
            cloud_params.append(
                {
                    'key': 'LETS_ENCRYPT_ENABLED',
                    'value': 'false'
                })
            cloud_params.append(
                {
                    'key': 'LETS_ENCRYPT_DOMAIN_NAME',
                    'value': ''
                })
            cloud_params.append(
                {
                    'key': 'LETS_ENCRYPT_EMAIL',
                    'value': ''
                })

        if os.environ['azure_datalake_enable'] == 'false':
            cloud_params.append(
                {
                    'key': 'AZURE_DATALAKE_TAG',
                    'value': ''
                })
            cloud_params.append(
                {
                    'key': 'AZURE_CLIENT_ID',
                    'value': ''
                })
            if os.environ['azure_oauth2_enabled'] == 'false':
                ssn_conf['ldap_login'] = 'true'
            ssn_conf['tenant_id'] = json.dumps(AzureMeta.sp_creds['tenantId']).replace('"', '')
            ssn_conf['subscription_id'] = json.dumps(AzureMeta.sp_creds['subscriptionId']).replace('"', '')
            ssn_conf['datalake_application_id'] = os.environ['azure_application_id']
            ssn_conf['datalake_store_name'] = None
        else:
            cloud_params.append(
                {
                    'key': 'AZURE_DATALAKE_TAG',
                    'value': ssn_conf['datalake_store_name']
                })
            cloud_params.append(
                {
                    'key': 'AZURE_CLIENT_ID',
                    'value': os.environ['azure_application_id']
                })
            ssn_conf['tenant_id'] = json.dumps(AzureMeta.sp_creds['tenantId']).replace('"', '')
            ssn_conf['subscription_id'] = json.dumps(AzureMeta.sp_creds['subscriptionId']).replace('"', '')
            ssn_conf['datalake_application_id'] = os.environ['azure_application_id']
            for datalake in AzureMeta.list_datalakes(ssn_conf['resource_group_name']):
                if ssn_conf['datalake_store_name'] == datalake.tags["Name"]:
                    datalake_store_name = datalake.name
        params = "--hostname {} --keyfile {} --datalab_path {} --os_user {} --os_family {} --request_id {} \
                 --resource {} --service_base_name {} --cloud_provider {} --billing_enabled {} --authentication_file {} \
                 --offer_number {} --currency {} --locale {} --region_info {}  --ldap_login {} --tenant_id {} \
                 --application_id {} --datalake_store_name {} --cloud_params '{}' --subscription_id {}  \
                 --validate_permission_scope {} --default_endpoint_name {} --keycloak_client_id {} \
                 --keycloak_client_secret {} --keycloak_auth_server_url {}". \
            format(ssn_conf['instnace_ip'], ssn_conf['ssh_key_path'], os.environ['ssn_datalab_path'],
                   ssn_conf['datalab_ssh_user'], os.environ['conf_os_family'], os.environ['request_id'],
                   os.environ['conf_resource'], ssn_conf['service_base_name'], os.environ['conf_cloud_provider'],
                   ssn_conf['billing_enabled'], ssn_conf['azure_auth_path'], os.environ['azure_offer_number'],
                   os.environ['azure_currency'], os.environ['azure_locale'], os.environ['azure_region_info'],
                   ssn_conf['ldap_login'], ssn_conf['tenant_id'], ssn_conf['datalake_application_id'],
                   ssn_conf['datalake_store_name'], json.dumps(cloud_params),
                   ssn_conf['subscription_id'], os.environ['azure_validate_permission_scope'],
                   ssn_conf['default_endpoint_name'],
                   os.environ['keycloak_client_name'], os.environ['keycloak_client_secret'],
                   os.environ['keycloak_auth_server_url'])
        subprocess.run("~/scripts/{}.py {}".format('configure_ui', params), shell=True, check=True)
    except Exception as err:
        traceback.print_exc()
        clear_resources()
        datalab.fab.append_result("Unable to configure UI.", str(err))
        sys.exit(1)

    try:
        logging.info('[SUMMARY]')

        print('[SUMMARY]')
        print("Service base name: {}".format(ssn_conf['service_base_name']))
        print("SSN Name: {}".format(ssn_conf['instance_name']))
        if os.environ['conf_network_type'] == 'public':
            print("SSN Public IP address: {}".format(ssn_conf['instnace_ip']))
            print("SSN Hostname: {}".format(ssn_conf['instance_dns_name']))
        else:
            print("SSN Private IP address: {}".format(ssn_conf['instnace_ip']))
        print("Key name: {}".format(os.environ['conf_key_name']))
        print("VPC Name: {}".format(ssn_conf['vpc_name']))
        print("Subnet Name: {}".format(ssn_conf['subnet_name']))
        print("Security groups Names: {}".format(ssn_conf['security_group_name']))
        print("SSN instance size: {}".format(os.environ['azure_ssn_instance_size']))
        ssn_conf['datalake_store_full_name'] = 'None'
        if os.environ['azure_datalake_enable'] == 'true':
            for datalake in AzureMeta.list_datalakes(ssn_conf['resource_group_name']):
                if ssn_conf['datalake_store_name'] == datalake.tags["Name"]:
                    ssn_conf['datalake_store_full_name'] = datalake.name
                    print("DataLake store name: {}".format(ssn_conf['datalake_store_full_name']))
            print("DataLake shared directory name: {}".format(ssn_conf['datalake_shared_directory_name']))
        print("Region: {}".format(ssn_conf['region']))
        jenkins_url = "http://{}/jenkins".format(ssn_conf['instance_host'])
        jenkins_url_https = "https://{}/jenkins".format(ssn_conf['instance_host'])
        print("Jenkins URL: {}".format(jenkins_url))
        print("Jenkins URL HTTPS: {}".format(jenkins_url_https))
        print("DataLab UI HTTP URL: http://{}".format(ssn_conf['instance_host']))
        print("DataLab UI HTTPS URL: https://{}".format(ssn_conf['instance_host']))

        try:
            with open('jenkins_creds.txt') as f:
                print(f.read())
        except Exception as err:
            print('Error: {0}'.format(err))
            print("Jenkins is either configured already or have issues in configuration routine.")

        with open("/root/result.json", 'w') as f:
            if os.environ['azure_datalake_enable'] == 'false':
                res = {"service_base_name": ssn_conf['service_base_name'],
                       "instance_name": ssn_conf['instance_name'],
                       "instance_hostname": ssn_conf['instance_host'],
                       "master_keyname": os.environ['conf_key_name'],
                       "vpc_id": ssn_conf['vpc_name'],
                       "subnet_id": ssn_conf['subnet_name'],
                       "security_id": ssn_conf['security_group_name'],
                       "instance_shape": os.environ['azure_ssn_instance_size'],
                       "region": ssn_conf['region'],
                       "action": "Create SSN instance"}
            else:
                res = {"service_base_name": ssn_conf['service_base_name'],
                       "instance_name": ssn_conf['instance_name'],
                       "instance_hostname": ssn_conf['instance_host'],
                       "master_keyname": os.environ['conf_key_name'],
                       "vpc_id": ssn_conf['vpc_name'],
                       "subnet_id": ssn_conf['subnet_name'],
                       "security_id": ssn_conf['security_group_name'],
                       "instance_shape": os.environ['azure_ssn_instance_size'],
                       "datalake_name": ssn_conf['datalake_store_full_name'],
                       "datalake_shared_directory_name": ssn_conf['datalake_shared_directory_name'],
                       "region": ssn_conf['region'],
                       "action": "Create SSN instance"}
            f.write(json.dumps(res))

        print('Upload response file')
        params = "--instance_name {} --local_log_filepath {} --os_user {} --instance_hostname {}". \
            format(ssn_conf['instance_name'], local_log_filepath, ssn_conf['datalab_ssh_user'], ssn_conf['instnace_ip'])
        subprocess.run("~/scripts/{}.py {}".format('upload_response_file', params), shell=True, check=True)
    except Exception as err:
        datalab.fab.append_result("Error with writing results.", str(err))
        sys.exit(1)
