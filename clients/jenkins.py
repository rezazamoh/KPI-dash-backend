import requests
from config import *


class JenkinsClient:

    def get_job(self, job_name):

        r = requests.get(
            f"{JENKINS_URL}/job/{job_name}/api/json",
            auth=(JENKINS_USER, JENKINS_TOKEN)
        )

        r.raise_for_status()
        return r.json()