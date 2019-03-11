from ScoutSuite.providers.aws.resources.resources import AWSResources
from ScoutSuite.providers.aws.aws import get_name
from ScoutSuite.providers.aws.utils import get_keys
import re


class EC2Instances(AWSResources):
    async def fetch_all(self, **kwargs):
        raw_instances = await self.facade.ec2.get_instances(self.scope['region'], self.scope['vpc'])
        for raw_instance in raw_instances:
            name, resource = await self._parse_instance(raw_instance)
            self[name] = resource

    async def _parse_instance(self, raw_instance):
        instance = {}
        id = raw_instance['InstanceId']
        instance['id'] = id
        instance['reservation_id'] = raw_instance['ReservationId']
        instance['monitoring_enabled'] = raw_instance['Monitoring']['State'] == 'enabled'
        instance['user_data'] = await self.facade.ec2.get_instance_user_data(self.scope['region'], id)
        instance['user_data_secrets'] = self._identify_user_data_secrets(instance['user_data'])

        get_name(raw_instance, instance, 'InstanceId')
        get_keys(raw_instance, instance, ['KeyName', 'LaunchTime', 'InstanceType', 'State', 'IamInstanceProfile', 'SubnetId'])

        instance['network_interfaces'] = {}
        for eni in raw_instance['NetworkInterfaces']:
            nic = {}
            get_keys(eni, nic, ['Association', 'Groups', 'PrivateIpAddresses', 'SubnetId', 'Ipv6Addresses'])
            instance['network_interfaces'][eni['NetworkInterfaceId']] = nic

        return id, instance

    @staticmethod
    def _identify_user_data_secrets(user_data):
        """
        Parses EC2 user data in order to identify secrets and credentials..
        """
        secrets = {}

        if user_data:
            aws_access_key_regex = re.compile('AKIA[0-9A-Z]{16}')
            aws_secret_access_key_regex = re.compile('[0-9a-zA-Z/+]{40}')
            rsa_private_key_regex = re.compile('(-----(\bBEGIN\b|\bEND\b) ((\bRSA PRIVATE KEY\b)|(\bCERTIFICATE\b))-----)')
            keywords = ['password', 'secret']

            aws_access_key_list = aws_access_key_regex.findall(user_data)
            if aws_access_key_list:
                secrets['aws_access_key'] = aws_access_key_list
            aws_secret_access_key_list = aws_secret_access_key_regex.findall(user_data)
            if aws_secret_access_key_list:
                secrets['aws_secret_access_key'] = aws_secret_access_key_list
            rsa_private_key_list = rsa_private_key_regex.findall(user_data)
            if rsa_private_key_list:
                secrets['rsa_private_key'] = rsa_private_key_list
            word_list = []
            for word in keywords:
                if word in user_data.lower():
                    word_list.append(word)
            if word_list:
                secrets['word'] = word_list

        return secrets
