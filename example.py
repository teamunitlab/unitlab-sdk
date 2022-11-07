from unitlab.core import upload_data
import os
if __name__ == "__main__":
    api_key = "<api>"
    task_id = "<task-id>"
    folder = "/path/"
    assert os.path.isdir(folder), "Folder does not exist"
    upload_data(folder, api_key, task_id)
