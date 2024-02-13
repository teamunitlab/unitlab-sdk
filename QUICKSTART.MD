First install the Unitlab.ai Python SDK using pip:
    pip install --upgrade unitlab

Import the necessary packages, and initialize the Unitlab client using your API key:
    from unitlab import UnitlabClient

    #An API key can be created https://app.unitlab.ai/UnitlabAI/api-keys.
    api_key = "YOUR API KEY"
    client = UnitlabClient(api_key)


Let's get a list of your projects programmatically using client.projects().
Note that this list will be retrieved under the user account corresponding to the API key.
#Result:
    [{'pk': '0ed69772-fd28-471b-b91c-2a57368c0dfb', 'name': '', 'parent_name': None, 'invoice': {'price': '0.00', 'images': 0}, 'annotator_progress': 0.0, 'reviewer_progress': 0.0, 'creator': 'user@gmail.com', 'created': '2023-04-11T11:00:23.737326+05:00'}, {'pk': '34738aec-b69b-4d30-9763-653017a68c02', 'name': 'human', 'parent_name': 'Red Blood Cell', 'invoice': {'price': '100.00', 'images': 1}, 'annotator_progress': 0.0, 'reviewer_progress': 0.0, 'creator': 'user@gmail.com', 'created': '2023-04-11T16:57:01.767677+05:00'},]

Add images to the project.
Now let's add images to the project which has not been created yet completely using client.project_upload_data():
#Code
    project_id = 'project_id' # a project id.      
    folder = '/home/user/DirOfPics/' # you can upload pictures(.jpg, .png) locally.    
    sample = client.project_upload_data(project_id, folder)
    
We can verify them using client.project('project_id') when project is fully created and images will be added to your images to do the project.