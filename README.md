# Developing

    py -m venv .
    .\Scripts\pip.exe install -e evcharge_status[DynamoDB]


# Cost model

Assumptions:
* Each invocation
  - Runs in a 512MB Lambda
  - Lambda is Arm architecture, not x86ish
  - Takes 5 seconds to run
  - Transfers 12KB in a message out to the internet to EVCharge.online
  - Transfers 4KB in a message out to the internet to Slack
  - Produces 10KB of logs
* Logs compress by a factor of 10
* Logs are retained for 30 days
* One DynamoDB record for a site is 1KB
* No backups
* No free-tier use available
* No custom metrics

Cost per invocation:

| Item                          | Price ($)            | Max cost per invocation($) |
| ----------------------------- | -------------------- | -------------------------- |
| EventBridge, custom event     | $1 per 1M            | $0.000001                  |
| Lambda invocation             | $0.2 per 1M          | $0.0000002                 |
| Lambda runtime                | $0.0000000067 per ms | $0.0000335                 |
| Data transfer out to EVCharge | $0.09 per GB         | $0.00000108                |
| DynamoDB read state           | $0.297 per 1M        | $0.0000000297              |
| DynamoDB write state*         | $1.4846 per 1M       | $0.0000014846              |
| Data transfer out to Slack*   | $0.09 per GB         | $0.00000036                |
| Collect logs                  | $0.05985 per GB      | $0.0000005985              |
| ----------------------------- | -------------------- | -------------------------- |
| Total                         |                      | $0.00003842757             |

General running costs:
| Item                          | Price ($)             | Max cost per annum ($) |
| ----------------------------- | --------------------- | ---------------------- |
| DynamoDB storage              | $0.29715 per GB-month | $0.0000035658          |
| Cloudwatch logs storage       | $0.0315 per GB-month  | $0.0163296             |
| Cloudwatch metrics            | 

Assuming it runs every 1 minute, annual running cost is ~$20.