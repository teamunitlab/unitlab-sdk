First install the Unitlab.ai Python SDK using pip:
    pip install --upgrade unitlab

Import the necessary packages, and initialize the Unitlab client using your API key:
    from unitlab import UnitlabClient

    #An API key can be created https://app.unitlab.ai/UnitlabAI/api-keys.
    api_key = "YOUR API KEY"
    client = UnitlabClient(api_key)


Let's get a list of your tasks programmatically using client.task_list().
Note that this list will be retrieved under the user account corresponding to the API key.
#Result:
    [{'pk': '0ed69772-fd28-471b-b91c-2a57368c0dfb', 'name': '', 'parent_name': None, 'invoice': {'price': '0.00', 'images': 0}, 'annotator_progress': 0.0, 'reviewer_progress': 0.0, 'creator': 'user@gmail.com', 'created': '2023-04-11T11:00:23.737326+05:00'}, {'pk': '34738aec-b69b-4d30-9763-653017a68c02', 'name': 'human', 'parent_name': 'Red Blood Cell', 'invoice': {'price': '100.00', 'images': 1}, 'annotator_progress': 0.0, 'reviewer_progress': 0.0, 'creator': 'user@gmail.com', 'created': '2023-04-11T16:57:01.767677+05:00'},]

Add images to the task.
Now let's add images to the task which has not been created yet completely using client.task_upload_data():
#Code
    task_id = 'task_id' # a task id.      
    folder = '/home/user/DirOfPics/' # you can upload pictures(.jpg, .png) locally.    
    sample = client.task_upload_data(task_id, folder)
    
We can verify them using client.task('task_id') when task is fully created and images will be added to your images to do the task.

Now let's request our images to the API directly, for instance to our ai-model car-segmentation which requires payment process. Note that api-key should be in the request header such as: Api-Key "YOUR API KEY"
#Request POST https://api.unitlab.ai/ocr/car-segmentation/:
    {
        "image_url":"https://unitlab-storage.s3.amazonaws.com/media/unitlaba-7373147e/taskimage/cars.jpg"
    }

#Response:
    
    { 
        "annotator": "annotator@gmail.com",
        "url": "https://unitlab-storage.s3.amazonaws.com/media/release-datasources/2dc39285-6ab2dbc328d84322a78544f2950699c8.jpg",
        "output":[
            "boxes": [
            {}
            ],
            "image": [
            ],
        ],
        "status": "labeled",
        "review_status": ""
    } 

You can get full list of APIs in API.MD file.
    
    