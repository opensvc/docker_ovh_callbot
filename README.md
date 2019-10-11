# OVH Phone Call Bot

Using a SIP phone line from French provider [OVH Telecom](https://www.ovhtelecom.fr), and a target phone number list. The bot loops over every phone number to deliver a text to speech message.

*Use case* : on urgent matter, wake up "on call" people through phone call

## Prerequisites

- [OVH SIP Line](https://www.ovhtelecom.fr/telephonie/voip/)
- [OVH Application Token](https://api.ovh.com/createToken/)
- Docker

## Environment Variables

### [Mandatory]

#### `OVH_ENDPOINT=ovh-eu`
Endpoint of API OVH Europe ([List of available endpoints](https://github.com/ovh/python-ovh#2-configure-your-application))
#### `OVH_APP_KEY=rIksDzjVfgRTsmAP`
OVH Application Key
#### `OVH_APP_SEC=1qEFGlks45FRGH234Abhdsjt99abDFRF`
OVH Application Secret
#### `OVH_CONS_KEY=EEJdlkzox4dkjb5nqiubf5jjSSF45flk`
OVH Consumer Key
#### `OVH_BILLING_ACCOUNT=vc12345-ovh-1`
OVH billing account name
#### `OVH_SIP_LINE_NUMBER=0033972012345`
OVH SIP line number which makes the calls
#### `BOT_NUMBER_LIST=0102030405,0203040506,0304050607`
The phone number list to contact

### [Optional]

#### `OVH_TEXT_MESSAGE="We all have two lives, the second begins when we realize we only have one"`
Text message being read when communication is established
#### `OVH_ANONYMOUS_CALL=False`
Present or not the OVH SIP line number
#### `OVH_CALL_TIMEOUT=20`
Ring duration
#### `BOT_WAIT_BEFORE_API_CHECK=30`
Once the call is requested on the api, we wait before requesting for its status
#### `BOT_WAIT_BEFORE_NEXT_CALL=10`
Once the call status is known, we sleep before initiating a new call
#### `BOT_TRY_COUNT_PER_NUMBER=1`
Number of times the bot will try to contact a single phone number
#### `BOT_RING_UNTIL_ANSWER=False`
With this parameter enabled, the bot will do an infinite loop, until someone actually takes the call

## Usage

### Step 1

Prepare `test.envfile`according to your environment

```
$ cat test.envfile 
OVH_ENDPOINT=ovh-eu
OVH_APP_KEY=rIksDzjVfgRTsmAP
OVH_APP_SEC=1qEFGlks45FRGH234Abhdsjt99abDFRF
OVH_CONS_KEY=EEJdlkzox4dkjb5nqiubf5jjSSF45flk
OVH_BILLING_ACCOUNT=vc12345-ovh-1
OVH_SIP_LINE_NUMBER=0033972012345
BOT_NUMBER_LIST=0102030405
OVH_TEXT_MESSAGE="Wake up, Wake up"
```

### Step 2

```
$ ./test.bash 
[<module>][2019-06-28 13:50:02.689931] Oncall Bot started at UTC 2019-06-28 13:50:02.677553

[oncall_loop][2019-06-28 13:50:02.690208] Calling number 0102030405
[ring_loop][2019-06-28 13:50:02.690576] Ringing 0102030405   [try 1/3]
[ring_loop][2019-06-28 13:50:03.064803]     => waiting 30 seconds before querying api for call status
[ring_loop][2019-06-28 13:50:33.495086]     => no answer
[ring_loop][2019-06-28 13:50:33.496267]     => waiting 10 seconds before next call
[ring_loop][2019-06-28 13:50:43.507922] Ringing 0102030405   [try 2/3]
[ring_loop][2019-06-28 13:50:44.046116]     => waiting 30 seconds before querying api for call status
[ring_loop][2019-06-28 13:51:14.143670]     => communication established at 2019-06-28T15:50:47+02:00 for 4 seconds
```

## OpenSVC integration

Using OpenSVC to orchestrate Docker container is an efficient way of automate stuff. Once the agent is installed, create a cluster secret to hold sensitive information, and then integrate either as a container, or as a task.

### Secret Creation

#### Create keys
```
$ om sec/ovhclient create
$ om sec/ovhclient add --key endpoint --value ovh-eu
$ om sec/ovhclient add --key application_key --value rIksDzjVfgRTsmAP
$ om sec/ovhclient add --key application_secret --value 1qEFGlks45FRGH234Abhdsjt99abDFRF
$ om sec/ovhclient add --key consumer_key --value EEJdlkzox4dkjb5nqiubf5jjSSF45flk
$ om sec/ovhclient add --key billing_account --value vc12345-ovh-1
$ om sec/ovhclient add --key sip_line_number --value 0033972012345
```

#### Display keys for secret
```
$ om sec/ovhclient keys
application_key
application_secret
billing_account
consumer_key
endpoint
sip_line_number
```


### Option 1 : As a container

#### deploy service

```
$ om mysvc deploy --config=opensvc.as.service.template.conf --kw env.num=1234567890 --kw env.msg=Hello
create mysvc
```

#### check service status
```
$ om mysvc print status 
mysvc                            up                                                           
`- instances            
   `- node                      up         idle, started 
      |- container#0    ........ up         docker google/pause                               
      `- container#1    ...O.... up         docker opensvc/ovh_callbot:latest                 
```

#### start calling numbers
```
$ om mysvc restart
```

#### destroy service

```
$ om mysvc purge
```

### Option 2 : As a task

#### deploy service

```
$ om mysvc deploy --config=opensvc.as.task.template.conf --kw env.num=1234567890 --kw env.msg=Hello
create mysvc
```

#### check service status
```
$ om mysvc print status
mysvc                            up                                                           
`- instances            
   `- node                      up         idle, started 
      |- container#0    ........ up         docker google/pause                               
      `- task#call      ...O.... n/a        docker opensvc/ovh_callbot:latest                 
                                            info: nostatus tag                                                 
```

#### start calling numbers manually
```
$ om mysvc run --rid task#call
node.mysvc.task#call   docker run --name=mysvc.task.call --label=com.opensvc.id=c750bc25-ce08-451a-b731-7d29666d2798.task#call --net=container:mysvc.container.0 --tty --cgroup-parent /opensvc.slice/mysvc.slice/task.slice/task.call.slice -e BOT_NUMBER_LIST=1234567890 -e OVH_TEXT_MESSAGE=Hello -e OVH_ENDPOINT -e OVH_APP_KEY -e OVH_APP_SEC -e OVH_CONS_KEY -e OVH_BILLING_ACCOUNT -e OVH_SIP_LINE_NUMBER opensvc/ovh_callbot:latest
node.mysvc.task#call   output:
node.mysvc.task#call   [<module>][2019-06-28 14:52:54.544182] Oncall Bot started at UTC 2019-06-28 14:52:54.532971
node.mysvc.task#call   
node.mysvc.task#call   [oncall_loop][2019-06-28 14:52:54.544475] Calling number 1234567890
node.mysvc.task#call   [ring_loop][2019-06-28 14:52:54.544858] Ringing 1234567890   [try 1/1]
node.mysvc.task#call   [ring_loop][2019-06-28 14:52:58.144269]     => waiting 30 seconds before querying api for call status
node.mysvc.task#call   [ring_loop][2019-06-28 14:53:28.264958]     => no answer
node.mysvc.task#call   [ring_loop][2019-06-28 14:53:28.266326]     => waiting 10 seconds before next call
node.mysvc.task#call   docker rm mysvc.task.call
```

#### add automatic schedule for task execution

Example : Schedule once between midnight and 2am every monday of even weeks


```
$ om mysvc set --kw task#call.schedule="00:00-02:00@121 mon %2"
```
Check OpenSVC scheduler configuration patterns [here](https://docs.opensvc.com/latest/agent.scheduler.html)


#### destroy service

```
$ om mysvc purge
```


## Disclaimer

OpenSVC and I are not responsible for any illegal usage of this software. 
