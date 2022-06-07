from src import client


def run():
    myclient = client.FTPClient("localhost", 9090)
    myclient.start()
