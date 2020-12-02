import json
import sys
from datetime import datetime

import requests

with open("dns.txt", "r") as file:
    dns = file.readlines()

server_url = "http://{}:8080/tasks/".format(dns[0])
cmds = ["--get_tasks", "--add_task", "--delete_tasks"]


def client_interface():
    # Check for invalid size of args
    if len(sys.argv) == 1:
        print("Available cmds: {}".format(cmds))
        return

    if sys.argv[1] == "--get_tasks":
        response = requests.get(server_url + "get_all")
        print(response.text)
        return

    elif sys.argv[1] == "--add_task" and len(sys.argv) == 4:
        task = json.dumps(
            {
                "title": sys.argv[2],
                "pub_date": datetime.now().isoformat(),
                "description": sys.argv[3],
            }
        )
        response = requests.post(server_url + "create", data=task)
        print(response.text)
        return

    elif sys.argv[1] == "--delete_tasks":
        response = requests.delete(server_url + "delete_all")
        print(response.text)
        return

    print("Available cmds: {}".format(cmds))


if __name__ == "__main__":
    client_interface()
