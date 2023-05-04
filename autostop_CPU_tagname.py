import boto3
import datetime
 
def lambda_handler(event, context):
    # Create CloudWatch client
    cloudwatch = boto3.client('cloudwatch')
 
    # Calculate the cutoff time for idle instances
    idle_cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
 
    # Retrieve all instances with a specific tag
    ec2 = boto3.client('ec2')
    instances = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:autostop', 'Values': ['true']},         #include your tag and value
            {'Name': 'instance-state-name', 'Values': ['running']}
        ]
    ).get('Reservations', [])
   
    print('---')
    if not instances:
        print("No Running Instances Found")
    else:
        #create an array to hold inactive instance ID's which should be shut down
        candidate_instances = []
        instance_id_name = dict()
        instance_name=None
       
        print("List of Running Instances")
        # Iterate through each instance
        for reservation in instances:
            for instance in reservation['Instances']:
                instance_id = instance.get('InstanceId')
                last_activity_time = None
                cpu_utilization = None
                activity_status = None
               
                # Get the launch time of the instance
                launch_time = instance.get('LaunchTime')
   
                # Get CPU utilization metric for the instance since launch time
                metric_data = cloudwatch.get_metric_data(
                    MetricDataQueries=[
                        {
                            'Id': 'm1',
                            'MetricStat': {
                                'Metric': {
                                    'Namespace': 'AWS/EC2',
                                    'MetricName': 'CPUUtilization',
                                    'Dimensions': [
                                        {
                                            'Name': 'InstanceId',
                                            'Value': instance_id
                                        },
                                    ]
                                },
                                'Period': 300,  # takes CPU utilization every 5 minutes
                                'Stat': 'Average',
                            },
                            'ReturnData': True,
                        },
                    ],
                    StartTime=(datetime.datetime.utcnow()- datetime.timedelta(hours=2)).isoformat(),
                    EndTime=datetime.datetime.utcnow().isoformat(),                   
                )
               
                # Check if there is any data for the metric
                if 'Values' not in metric_data['MetricDataResults'][0]:
                    # If there is no data, consider the instance as inactive
                    activity_status = 'Inactive'
                    last_activity_time = 'N/A'
                    candidate_instances.append(instance_id) #instance considered for shutdown
               
                # checking if data exists within the MetricDataResults. If the instance has been initialized for less time than period defined,
                # then the dataset will be null. in this case, instance should considered active
                elif not metric_data['MetricDataResults'][0]['Values']:
                    print('MetricDataResults array is empty because instance was recently started')
                    activity_status = 'Active'
                else:
                    # If there is data, get the last CPU utilization value
                    cpu_utilization = metric_data['MetricDataResults'][0]['Values'][-1]
   
                    # If the CPU utilization is below 10%, consider the instance as inactive
                    if cpu_utilization < 10:
                        activity_status = 'Inactive'
                        last_activity_time = max(metric_data['MetricDataResults'][0]['Timestamps'])
                        candidate_instances.append(instance_id) #instance considered for shutdown
                    else:
                        activity_status = 'Active'
                        last_activity_time = max(metric_data['MetricDataResults'][0]['Timestamps'])
                       
                #generate key-value pair for future reference of instance name
                for tag in instance["Tags"]:
                    if tag["Key"] == 'Name':
                        instance_name=tag["Value"]
                instance_id_name[instance_id] = instance_name
               
                # Print out the instance ID, CPU utilization, and activity status
                print("Instance ID: %s, CPU Utilization: %7.4f%%, Activity Status: %8s, Instance Name: %s" % (instance_id, cpu_utilization, activity_status, instance_name))
 
 
        stopinstancecount=0
        #shutdown the inactive instances
        if candidate_instances:
            print('---')
            print('Instances found requiring shutdown:')
            #"""
            response = ec2.stop_instances(InstanceIds=candidate_instances)
           
            for instance in response['StoppingInstances']:
                print(f"Instance ID: {instance['InstanceId']}, Current State: {instance['CurrentState']['Name']}, Previous State: {instance['PreviousState']['Name']}, Instance Name: {instance_id_name[instance['InstanceId']]}")
                if instance['CurrentState']['Name']=='stopping':
                    stopinstancecount=stopinstancecount+1
            print('---')
            print(f"Number of stopped instances: {stopinstancecount}/{len(response['StoppingInstances'])}")
            #"""
        else:
            print('No instances found requiring shutdown')
    print('---')
 
if __name__ == '__main__':
    lambda_handler(None, None)
