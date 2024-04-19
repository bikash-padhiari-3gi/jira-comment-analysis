import json
import boto3
import os
# import requests

region_name = 'ap-south-1'

comprehend = boto3.client(service_name='comprehend', region_name=region_name)
sns = boto3.client('sns')
topic_arn = os.environ.get('SNS_TOPIC_ARN')
# topic_arn = 'arn:aws:sns:ap-south-1:590183768298:jira-analysis-topic'

def lambda_handler(event, context):
    # print(event)
    body = json.loads(event['body'])
    # print("BODY------------",body)
    
    project_key = body['issue']['fields']['project']['key']
    issue_key = body['issue']['key']
    reporter_display_name = body['issue']['fields']['reporter']['displayName']
    if body['issue']['fields']['assignee'] is not None:
        assignee_display_name = body['issue']['fields']['assignee']['displayName']
    else:
        assignee_display_name = "Unassigned"

    comment_key= body['comment']['id']
    comment = body['comment']
    print(comment)
    comment_text = comment['body']
  
    if project_key!="KAN":
        sentiment = detect_sentiment(comment_text)
        print("SENTIMENT : ", sentiment)
    
        message = f'Negative Comment\n Project: {project_key}\n Issue : {issue_key} \n Comment : {comment_text}\n Assignee : {assignee_display_name}\n Reporter : {reporter_display_name}\n '
        if sentiment == 'NEGATIVE':
            response = sns.publish(
                TopicArn=topic_arn,
                Message=message
            )

    return {
        'statusCode': 200,
        'body': json.dumps({'status': 'received'})
    }

def detect_sentiment(text):
    response = comprehend.detect_sentiment(Text=text, LanguageCode='en')
    return response['Sentiment']
