import socket
import os
import json

import sys

import time
from src import protocol

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FTPClient(object):
    def __init__(self, ip, port):
        self.client = socket.socket()
        self.ip = ip
        self.port = port

    def cmd_help(self, *args):
        msg = """
        ------------可用命令------------
        ls              列出当前目录下文件
        pwd             显示当前文件路径
        cd ../..        进入指定目录
        get filename    下载指定文件
        put filename    上传指定文件
        mkdir filename  创建目录
        rm filename     删除指定文件
        exit            退出
        """
        print(msg)

    def cmd_rm(self, *args):  # 删除指定文件

        cmd_split = args[0].split()
        if len(cmd_split) > 1:
            filename = cmd_split[1]
            self.client.send(protocol.Protocol.json_rm(filename).encode())
            res_rm = json.loads(self.client.recv(1024).decode())
            status = res_rm["status"]
            if status == "404":
                print("文件不存在!")
            elif status == "200":
                self.total = res_rm["total"]
                self.available = res_rm["available"]
                print("文件删除成功")
                print("总大小为: \t%.2f MB \t(%d B)" % (self.total / 1024 ** 2, self.total))
                print("可用空间为: \t%.2f MB \t(%d B)" % (self.available / 1024 ** 2, self.available))

    def cmd_mkdir(self, *args):  # 创建目录
        cmd = args[0]
        cmd_split = cmd.split()
        if len(cmd_split) > 1:
            self.client.send(protocol.Protocol.json_mkdir(cmd).encode())

    def cmd_cd(self, *args):  # 进入指定目录
        cmd_split = args[0].split()
        if len(cmd_split) > 1:
            dir_name = cmd_split[1]
            self.client.send(protocol.Protocol.json_cd(dir_name).encode())
            res_cd = json.loads(self.client.recv(1024).decode())
            status = res_cd["status"]
            if status == "404":
                print("目录不存在!")

    def cmd_pwd(self, *args):  # 显示当前目录路径
        self.client.send(protocol.Protocol.json_pwd().encode())
        res_pwd = self.client.recv(1024).decode()
        print("当前路径: %s" % res_pwd)

    def cmd_exit(self, *args):  # 退出客户端
        exit()

    def start(self):  # 开启客户端
        self.__connect(self.ip, self.port)
        self.__auth()
        self.__interactive()

    def __connect(self, ip, port):  # 客户端连接服务端
        self.client.connect((ip, port))

    def __auth(self):  # 客户端认证
        account = input("请输入用户名>>:").strip()
        password = input("请输入密码>>:").strip()
        self.client.send(protocol.Protocol.json_auth(account, password).encode())
        server_response = json.loads(self.client.recv(1024).decode())
        status = server_response["status"]
        if status == "200":
            self.total = server_response["total"]
            self.available = server_response["available"]
            self.path = "%s/data/downloads" % BASE_DIR
            print("总大小为: \t%.2f MB \t(%d B)" % (self.total / 1024 ** 2, self.total))
            print("可用空间为: \t%.2f MB \t(%d B)" % (self.available / 1024 ** 2, self.available))
        else:
            print("用户名或密码错误!")
            self.cmd_exit()

    def __interactive(self):  # 连接成功后开启的交互程序
        while True:
            cmd = input("请输入指令>>:").strip()
            if len(cmd) == 0:
                continue
            cmd_str = cmd.split()[0]
            if hasattr(self, "cmd_%s" % cmd_str):
                func = getattr(self, "cmd_%s" % cmd_str)
                func(cmd)
            else:
                self.cmd_help()

    def cmd_ls(self, *args):  # ls指令：列举当前目录下的文件
        self.client.send(protocol.Protocol.json_ls().encode())
        result_size = json.loads(self.client.recv(1024).decode())
        self.client.send(protocol.Protocol.json_ls().encode())
        size = result_size["resultsize"]
        received_size = 0
        while received_size < size:
            result = self.client.recv(1024).decode()
            received_size += len(result)
            print("%s" % result)

    def cmd_put(self, *args):  # 上传文件
        cmd_split = args[0].split()
        if len(cmd_split) > 1:
            filepath = cmd_split[1]
            filename = filepath.split('/')[-1]
            if os.path.isfile(filepath):
                filesize = os.path.getsize(filepath)
                json_msg_dic = protocol.Protocol.json_put(filename, filesize)
                self.client.send(json_msg_dic.encode())
                server_response = json.loads(self.client.recv(1024).decode())  # 防止粘包，等服务器确认
                status = server_response["status"]
                if status == "200":
                    self.total = server_response["total"]
                    self.available = server_response["available"]
                    send_size = 0
                    with open(filepath, "rb") as f:
                        for line in f:
                            self.client.send(line)
                            send_size += len(line)
                            self.progress(int(100 * (send_size / filesize)))
                        else:
                            print("\n文件 [%s] 上传成功" % filename)
                            print("总大小为: \t%.2f MB \t(%d B)" % (self.total / 1024 ** 2, self.total))
                            print("可用空间为: \t%.2f MB \t(%d B)" % (self.available / 1024 ** 2, self.available))
                elif status == "300":
                    print("可用空间为: \t%.2f MB \t(%d B)" % (self.available / 1024 ** 2, self.available))
                    print("当前文件大小为: \t%.2f MB \t(%d B)" % (filesize / 1024 ** 2, filesize))
                    print("可用空间不足!")
            else:
                print("文件 [%s] 不存在!" % filename)

    def cmd_get(self, *args):  # 下载文件
        cmd_split = args[0].split()
        if len(cmd_split) > 1:
            filename = cmd_split[1]
            filepath = "%s/%s" % (self.path, cmd_split[1])
            self.client.send(protocol.Protocol.json_get(filename, 0).encode())
            server_response = json.loads(self.client.recv(1024).decode())
            status = server_response["status"]
            if status == "200":
                received_size = 0
                filesize = server_response["filesize"]
                self.client.send(protocol.Protocol.json_get(filename, filesize).encode())
                with open(filepath, "wb") as f:
                    while received_size < filesize:
                        data = self.client.recv(1024)
                        received_size += len(data)
                        f.write(data)
                        self.progress(int(100 * (received_size / filesize)))
                    else:
                        print("\n文件 [%s] 下载完毕" % filename)
            elif status == "404":
                print("文件 [%s] 不存在!" % filename)

    def progress(self, percent, width=50):  # 进度条打印
        if percent >= 100:
            percent = 100
        show_str = ('[%%-%ds]' % width) % (int(width * percent / 100) * "#")  # 字符串拼接的嵌套使用
        print("\r%s %d%%" % (show_str, percent), end='', file=sys.stdout, flush=True)
