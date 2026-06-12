Webhooks

\> \#\# Documentation Index  
\> Fetch the complete documentation index at: https://docs.followupboss.com/llms.txt  
\> Use this file to discover all available pages before exploring further.

\# Webhooks

Use webhooks to be notified about events that happen in a Follow Up Boss account.

\> 🚧 Owner Permissions Required  
\>  
\> Only the owner has access to creating, updating, or deleting webhooks.

\# Overview

Webhooks post JSON to a specific URL every time an event listed below is triggered. Webhooks remove the need to poll for changes. When an event occurs--for example a person is assigned to a different agent, this event will be sent to your system as an HTTP POST to the webhook URL configured for the \`peopleUpdated\` event.

Examples of what you might use webhooks for:

\* Update a person's name in your database when it is changed in Follow Up Boss  
\* Update a person's email or phone in your database when it is changed in Follow Up Boss  
\* Re-assign a person in your system when it is re-assigned in Follow Up Boss  
\* When a Zillow lead is added to Follow Up Boss you add it to your IDX search website

\> 📘 Batch Updates  
\>  
\> The following actions can result in a large number of people updates:  
\>  
\> \* Tags added or removed  
\> \* Stage updated  
\> \* Source updated  
\> \* Agent re-assigned  
\> \* Lender re-assigned  
\>  
\> If one of these actions result in a large number of people being updated, the webhook event notification may be split into multiple requests.

\# Supported webhook events

\#\# People

\`peopleCreated\`, \`peopleUpdated\`, \`peopleDeleted\`, \`peopleTagsCreated\`, \`peopleStageUpdated\`,\`peopleRelationshipCreated\`,\`peopleRelationshipUpdated\`,\`peopleRelationshipDeleted\`

\#\#\# peopleUpdated

One or more of the following fields are updated in a person:

\* Name \`name\` \`firstName\` \`lastName\`  
\* Emails \`emails\`  
\* Phone Numbers \`phones\`  
\* Address \`addresses\`  
\* Price \`price\`  
\* Background \`background\`  
\* Assigned Agent \`assignedTo\` \`assignedUserId\`  
\* Assigned Lender \`assignedLenderName\` \`assignedLenderId\`  
\* Contacted \`contacted\`  
\* Stage \`stage\` \`stageId\`  
\* Lead Source \`source\` \`sourceUrl\`  
\* Tags \`tags\`  
\* Custom Fields  
\* Relationship is created, updated, or deleted

\> 📘 Custom Fields  
\>  
\> If you want to view custom field data following a \`peopleUpdated\` event, make sure you add the query parameter \`fields=allFields\` to your \`GET /people\` request, custom fields are not returned by default.

\#\#\# peopleDeleted

When a person is deleted all associated data is deleted as well e.g. notes, calls, text messages, etc. There will not be any delete events triggered for these resources when this happens.

JSON sample of event notification:

\`\`\`  
{  
    "eventId": "64d0ad74-3aab-4b30-89c9-7337398cf8b4",  
    "eventCreated": "2016-12-12T15:19:21+00:00",  
    "event": "peopleDeleted",  
    "resourceIds": \[1234,5322,29456\],  
    "uri": null  
}  
\`\`\`

\#\#\# peopleTagsCreated

When a tag is added to a person, the payload will include the name of the new tag. Multiple tags and person ids may be included. Note: The webhook will fire regardless of whether a tag was previously removed and re-added to a contact.

JSON sample of event notification:

\`\`\`  
{  
    "eventId": "e8d9f150-5dac-4c53-8c0f-06560dc4ec08",  
    "eventCreated": "2019-07-01T17:22:28+00:00",  
    "event": "peopleTagsCreated",  
    "resourceIds": \[  
        40773,  
        40772  
    \],  
    "uri": "https://api.followupboss.com/v1/people?id=40773,40772",  
    "data": {  
        "tags": \[  
            "Kingsbury"  
        \]  
    }  
}  
\`\`\`

\#\#\# peopleStageUpdated

When a person's stage is updated, the payload will include the name of the new stage.

JSON sample of event notification:

\`\`\`  
{  
    "eventId": "e0ac086a-879a-4d8b-869a-fe53151e34f4",  
    "eventCreated": "2019-07-01T17:12:32+00:00",  
    "event": "peopleStageUpdated",  
    "resourceIds": \[  
        40942  
    \],  
    "uri": "https://api.followupboss.com/v1/people?id=40942",  
    "data": {  
        "stage": "Free Trial"  
    }  
}  
\`\`\`

\#\# Notes

\`notesCreated\`, \`notesUpdated\`, \`notesDeleted\`

\#\# Reactions (Beta)

\`reactionCreated\`,\`reactionDeleted\`

\`\`\`  
{  
    "eventId": "e0ac086a-879a-4d8b-869a-fe53151e34f4",  
    "eventCreated": "2019-07-01T17:12:32+00:00",  
    "event": "reactionCreated",  
    "resourceIds": \[9387\],  
    "uri": "https://api.followupboss.com/v1/reactions/9387",  
    "data": {  
        "refType": "Note",  
        "refId": 3827,  
        "refUri": "https://api.followupboss.com/v1/notes/3827?includeReactions=true"  
    }  
}  
\`\`\`

\#\# Threaded Replies (Beta)

\`threadedReplyCreated\`, \`threadedReplyUpdated\`, \`threadedReplyDeleted\`

\`\`\`  
{  
    "eventId": "e0ac086a-879a-4d8b-869a-fe53151e34f4",  
    "eventCreated": "2019-07-01T17:12:32+00:00",  
    "event": "threadedReplyCreated",  
    "resourceIds": \[9387\],  
    "uri": "https://api.followupboss.com/v1/threadedReplies/9387",  
    "data": {  
        "refType": "Note",  
        "refId": 3827,  
        "refUri": "https://api.followupboss.com/v1/notes/3827?includeThreadedReplies=true"  
    }  
}  
\`\`\`

\#\# Emails

\`emailsCreated\`, \`emailsUpdated\`, \`emailsDeleted\`

\#\# Tasks

\`tasksCreated\`, \`tasksUpdated\`, \`tasksDeleted\`

\#\# Appointments

\`appointmentsCreated\`, \`appointmentsUpdated\`, \`appointmentsDeleted\`\\  
These webhooks only fires when the appointment was created in Follow Up Boss, not when we sync appointments created on Integrated Calendars (i.e. Google or Office 365 calendars).

\#\# Text Messages

\`textMessagesCreated\`, \`textMessagesUpdated\`, \`textMessagesDeleted\`

\#\# Calls

\`callsCreated\`, \`callsUpdated\`, \`callsDeleted\`

\#\# Email Marketing Events

\`emEventsOpened\`\\  
People open an email marketing email.

\`emEventsClicked\`\\  
People click a link in an email marketing email.

\`emEventsUnsubscribed\`\\  
People unsubscribe from email marketing emails.

\#\# Deals

\`dealsCreated\`, \`dealsUpdated\`, \`dealsDeleted\`

\> 📘 \`dealsUpdated\` Event  
\>  
\> This event does \*\*not\*\* fire for \`files\` being changed on the deal.

\#\# Stages

\`stageCreated\`, \`stageUpdated\`, \`stageDeleted\`

\> 🚧 Stage Events  
\>  
\> The Stage-specific webhooks are used when the values of the Stage field are changed in the admin area (or API) of Follow Up Boss and \*\*not when the Stage is changed for a lead\*\*.  
\>  
\> The primary use case for these events is for integrations that need to know when the name of a stage has been added, updated, or removed.

\#\# People Events

\`eventsCreated\`\\  
People perform an action on your IDX website, e.g. view a property.

\#\# Pipeline Events

\`pipelineCreated\` \`pipelineUpdated\` \`pipelineDeleted\`\\  
A pipeline is created, updated, or deleted in the system.

\> 📘 \`pipelineUpdated\` Event  
\>  
\> 1\. This event triggers when any \*\*Pipeline\*\* property is updated.  
\> 2\. Additionally, when a pipeline's order weight is changed, it may also trigger additional \`pipelineUpdated\` events for other pipelines whose order weights are automatically adjusted.

\#\# Pipeline Stage Events

\`pipelineStageCreated\` \`pipelineStageUpdated\` \`pipelineStageDeleted\`\\  
A pipeline stage is created, updated, or deleted.

\> 📘 Pipeline stage events  
\>  
\> 1\. This event triggers when any \*\*Pipeline Stage\*\* property is updated.  
\> 2\. Additionally, when a pipeline stage's order weight is changed, it may also trigger additional \`pipelineStageUpdated\` events for other pipeline stages whose order weights are automatically adjusted.

\#\# Custom Fields Events

\`customFieldsCreated\` \`customFieldsUpdated\` \`customFieldsDeleted\`\\  
Custom fields are created, updated or deleted.

\> 🚧 Custom Field Properties Only  
\>  
\> Note that this webhook is specific to the custom field configuration only, not the values.

\> 📘 \`customFieldsUpdated\` Event  
\>  
\> 1\. This event triggers when any \*\*Custom field\*\* property is updated.  
\> 2\. Additionally, when a custom field's order weight is changed, it may also trigger additional \`customFieldsUpdated\` events for other custom fields whose order weights are automatically adjusted.

\#\# Deal Custom Fields Events

\`dealCustomFieldsCreated\` \`dealCustomFieldsUpdated\` \`dealCustomFieldsDeleted\`\\  
Deal custom fields are created, updated or deleted.

\> 🚧 Deal Custom Field Properties Only  
\>  
\> Note that this webhook is specific to the deal custom field configuration only, not the values.

\> 📘 \`dealCustomFieldsUpdated\` Event  
\>  
\> 1\. This event triggers when any \*\*Deal custom field\*\* property is updated.  
\> 2\. Additionally, when a deal custom field's order weight is changed, it may also trigger additional \`dealCustomFieldsUpdated\` events for other deal custom fields whose order weights are automatically adjusted.

\# Registering a webhook

Send an HTTPS POST to the \[\`/v1/webhooks\`\](https://docs.followupboss.com/reference/webhooks-post) endpoint with a JSON object that specifies the event and callback URL.

\> 🚧 Limited number of webhooks per event  
\>  
\> There is a limit of \*\*two\*\* web hooks per event per system which can be registered.  
\>  
\> Unused webhooks should be unregistered to prevent hitting the limit. In order to unregister a webhook, first call the GET \[\`/v1/webhooks\`\](https://docs.followupboss.com/reference/webhooks-get) API with the account owner API key and the X-System header that you are using for the webhook subscriptions to retrieve the list of webhooks that are registered along with the IDs. From there, make a call to the DELETE \[\`/v1/webhooks/:id\`\](https://docs.followupboss.com/reference/webhooks-delete-id)  API and unregister any unused webhooks.  
\>  
\> If multiple endpoints for an event are desired, a single webhook should be registered which in turn handles the fan out to multiple endpoints internally to your system. Keep in mind the best practices below about de-coupling the message receiving and workload so that the initial call does not timeout.

\> 🚧 Webhook Security  
\>  
\> When registering a webhook, you should use a unique identifier that maps a user to your system. \*\*Do not use API keys as part of a URL request.\*\*

\> ❗️ HTTPS Only  
\>  
\> Callback URLs must be a secure endpoint.

\> ❗️ X-System Header is Required  
\>  
\> The X-System HTTP Header is required for all requests to /v1/webhooks endpoints.

\`\`\`http  
POST /v1/webhooks HTTP/1.1  
Content-Type: application/json  
X-System: AcmeLeadProvider  
...  
{  
  "event": "peopleCreated",  
  "url": "https://acmeLeadProvider.com/callbacks/fub/peopleCreated"  
}  
\`\`\`

The response will be JSON encoded representation of the webhook created.

\`\`\`json  
{  
  "id": 1244,  
  "status": "Active",  
  "event": "peopleCreated",  
  "url": "https://acmeLeadProvider.com/callbacks/fub/peopleCreated"  
}  
\`\`\`

\# Receiving webhook events

Create an endpoint that accepts HTTP POST requests at the URL specified in the registered webhook. The body of the request will be JSON encoded. To acknowledge the receipt, your endpoint should respond within 10 seconds with a \`2XX\` HTTP status code such as \`200\` or \`204\`. Any other response will indicate that you did not receive the webhook and we will continue to retry at various intervals for up to 8 hours.

For example, the endpoint at \`https://acmeleadprovider.com/callbacks/fub/peoplecreated\` would receive the following HTTP POST when a person is created in Follow Up Boss:

\`\`\`http  
POST /callbacks/fub/peoplecreated HTTP/1.1  
Content-Type: application/json  
...  
{  
  "eventId": "152d60c0-79da-4018-a9af-28aec8a71c94",  
  "eventCreated": "2016-12-12T15:19:21+00:00",  
  "event": "peopleCreated",  
  "resourceIds": \[1234,3244,3232\],  
  "uri": "https://api.followupboss.com/v1/people?id=1234,3244,3232"  
}  
\`\`\`

\# Retrying webhook events

Upon receiving status codes less than \`200\` and greater than or equal to \`300\` from your system, Follow Up Boss will attempt to retry the request up to 5 times. The retry timing works as follows:

Attempt 1 → 2: Wait 1 minute (60 seconds)\\  
Attempt 2 → 3: Wait 5 minutes (300 seconds)\\  
Attempt 3 → 4: Wait 5 minutes (300 seconds)\\  
Attempt 4 → 5: Wait 10 minutes (600 seconds)\\  
Attempt 5 → 6: Wait 30 minutes (1800 seconds)

\# Verify the request

With each request, we pass along a \`FUB-Signature\` header. You can use this string value to verify the request is from us using your X-System-Key provided when you registered your system.

You will want to base64 encode the JSON payload you received from the request (non-prettified), then produce a SHA256 hash with this base64 encode value and your X-System-Key , this value should match the FUB-Signature value.

\`\`\`php  
function isFromFollowUpBoss(string $context, string $signature): boolean {  
    $calculated \= hash\_hmac('sha256', base64\_encode($context), YOUR\_X-SYSTEM-KEY);

    return $signature \=== $calculated;  
}

if (isFromFollowUpBoss($jsonPayload, $signatureFromHeader)) {  
    // do something  
}  
\`\`\`

\# Handling webhook events

The endpoint that handles events should do an HTTP GET to the resource URI specified in the event. Then compare the response to the local database and apply changes that are found.

See the code samples below for handling webhook events:

\`\`\`php  
\<?php  
const FUB\_API\_KEY \= 'API Key for an Admin user in the Follow Up Boss Account';

// Retrieve the request's body and parse it as JSON  
$input \= @file\_get\_contents("php://input");  
$event\_json \= json\_decode($input);

$event \= $event\_json-\>{'event'};  
$resource\_uri \= $event\_json-\>{'uri'};

// for peopleCreated and peopleUpdated events fetch the people  
// at the resource URI

$curl \= curl\_init($resource\_uri);

$headers \= array(  
    'Authorization: Basic '. base64\_encode(FUB\_API\_KEY . ":")  
);

curl\_setopt($curl, CURLOPT\_HTTPHEADER, $headers);  
curl\_setopt($curl, CURLOPT\_RETURNTRANSFER, true);

$result \= curl\_exec($curl);  
curl\_close($curl);

$remote\_records \= json\_decode($result);

// Compare the remote record with your local record

http\_response\_code(200); // PHP 5.4 or greater

echo('OK');  
\`\`\`

\# Requesting webhook events

Individual webhook events can be requested from \[\`/v1/webhookEvents/:id\`\](https://docs.followupboss.com/reference/webhookeventsuuid). This can useful if your system was unavailable to receive events for some reason and there are events older than 3 days that were missed.

\> 🚧 Webhook Event Retries  
\>  
\> If your system is unavailable or responds with an HTTP status code other than \`2XX\` such as \`200\` or \`204\`, FUB will continue to retry for up to 8 hours.

\# Disabling webhooks

In order to disable a webhook manually, you need to call the DELETE event for \[\`/v1/webhooks/\`\](https://docs.followupboss.com/reference/webhooks-delete-id) with the corresponding ID for your registered webhook.

\> 👍 Automatic Webhook Disabling  
\>  
\> It is recommended that you set up your webhooks to return an HTTP code of \`406\` or \`410\` when you want them deleted automatically (such as when a customer is no longer utilizing your system).  
\>  
\> Additionally, Follow Up Boss will automatically disable webhooks that have significant failures (greater than 50% over a 48 hour period) if they have not recovered on their own within a week's time.

\<br /\>

\# Webhook best practices

Setup your system to de-couple receiving webhook events from fetching the resource specified in the event. For example--the web service that receives events could record the event in a local database table. A separate backend process could be created to monitor this table for new rows and fetch the resource specified in the event. By separating these, the web service that handles receiving webhooks is doing less and is, therefore less likely to fail. The process that processes the events can contain all the complex logic to fetch the resource from Follow Up Boss, reconcile with your local system and mark the event as processed in the table. If this process fails or breaks it can be debugged independently of the web service. The table that stores events is the source of truth as to what webhook events have been received and processed.

\# Debugging webhooks

Since webhooks require a publicly accessible URL to function they can be hard to test from your local machine. It is recommended that you use a service like \[Request Bin\](https://requestbin.com/) when you are developing your webhook endpoints.

\# Common webhook mistakes

\* Make sure you provide the correct URL when registering a webhook. You can list all your webhooks at the \[\`/v1/webhooks\`\](https://docs.followupboss.com/reference/webhooks-get) endpoint.  
\* Make sure the webhook endpoint is returning a \`2XX\` HTTP status code such as \`200\`  
\* When registering a webhook make sure you are setting the \`X-System\` header. You can also include the system param in the query string or post data. For example: \`https://api.followupboss.com/v1/webhooks/32?system=AcmeCo\`  
\* If you are setting up webhooks for multiple Follow Up Boss accounts be sure to include a Follow Up Boss account identifier in the registered webhook URLs. Your webhook URLs should look like this: \`https://acmeLeadProvider.com/callbacks/fub/account12/peopleCreated\` or \`https://acmeLeadProvider.com/callbacks/fub/peopleCreated?fub\_account=12\`

\# Inbox App webhooks

Inbox App webhooks behave differently from other Follow Up Boss webhooks and can not be updated using \`/v1/webhooks\` APIs. Please see the \[Inbox Apps webhooks guide\](https://docs.followupboss.com/docs/inbox-apps-webhooks) for information on available Inbox App webhooks.

