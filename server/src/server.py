import socketserver
import json
import os
import datetime

from src import protocol
from src import update

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = open(BASE_DIR + "\\log\\log.txt", 'a')


class MyTCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        while True:  # while True
            try:
                self.data = self.request.recv(1024).strip()  # 接受客户端数据
                if not self.data:
                    break
                print(datetime.datetime.now(), file=LOG_FILE, end="\t")
                print("{} 发送请求:".format(self.client_address[0]), file=LOG_FILE, end="\t")

                cmd_dic = json.loads(self.data.decode())
                print(cmd_dic, file=LOG_FILE)
                action = cmd_dic["action"]  # 获取操作
                if hasattr(self, action):  # 匹配操作
                    func = getattr(self, action)
                    func(cmd_dic)
            except Exception as e:
                print(datetime.datetime.now(), file=LOG_FILE, end="\t")
                print(e, file=LOG_FILE)

    def auth(self, *args):  # 客户端认证
        cmd_dic = args[0]
        account = cmd_dic["account"]
        password = cmd_dic["password"]
        user_file = "%s/data/%s/user_info" % (BASE_DIR, account)
        if os.path.isfile(user_file):
            with open(user_file) as f:
                user_info = json.load(f)
                user_password = user_info["password"]
                if password == user_password:  # 获取密码并判断
                    self.request.send(protocol.Protocol.json_auth(
                        total=user_info["total"], available=user_info["available"]).encode())  # 服务端返回登录信息
                    os.chdir("%s/data/%s/root" % (BASE_DIR, account))  # 切换目录
                    self.path = "%s/data/%s/root" % (BASE_DIR, account)  # 设置登录用户的信息
                    self.total = user_info["total"]
                    self.available = user_info["available"]
                    self.user_file = user_file
                else:
                    self.request.send(protocol.Protocol.json_auth(status="404").encode())  # 密码错误
        else:
            self.request.send(protocol.Protocol.json_auth(status="404").encode())  # 文件不存在

    def mkdir(self, *args):  # 创建目录
        cmd_dic = args[0]
        cmd = cmd_dic["cmd"]
        dirname = cmd.split()[1]  # 获取目录名称
        check = os.popen("ls | grep -w " + dirname).read()  # 检查文件是否有重名文件或文件夹
        if not check:
            os.popen(cmd)
            self.request.send(protocol.Protocol.json_mkdir(cmd="", status="200").encode())  # 服务器返回数据
        else:
            self.request.send(protocol.Protocol.json_mkdir(cmd="", status="404").encode())  # 服务器返回数据

    def pwd(self, *args):  # 显示当前路径
        path = "\\" + os.path.relpath(os.path.curdir, self.path)
        self.request.send(path.encode())

    def getdirsize(self, dirname):  # 计算文件夹大小
        size = 0
        for root, dirs, files in os.walk(dirname):
            size += sum([os.path.getsize(os.path.join(root, name)) for name in files])
        return size

    def rm(self, *args):  # 删除指定文件
        cmd_dic = args[0]
        filename = cmd_dic["filename"]  # 获取文件名
        if os.path.isfile(filename) or os.path.isdir(filename):  # 检查文件是否存在
            if os.path.isfile(filename):
                filesize = os.path.getsize(filename)
                os.remove(filename)  # 删除文件
            else:
                filesize = self.getdirsize(filename)  # 获取文件大小
                os.popen("rm -rf " + filename)  # 删除目录

            self.available += filesize
            update.update_available(self.user_file, self.available)  # 更新用户可用剩余空间
            self.request.send(
                protocol.Protocol.json_rm(status="200", total=self.total, available=self.available).encode())  # 服务器返回数据
        else:
            self.request.send(protocol.Protocol.json_rm(status="404").encode())

    def cd(self, *args):  # 进入指定目录
        cmd_dic = args[0]
        dir_name = cmd_dic["dirname"]
        path = "%s/%s" % (os.path.abspath(os.path.curdir), dir_name)  # 获取某些path信息
        old_path = "%s" % (os.path.abspath(os.path.curdir))
        root_path = "%s" % (os.path.abspath(self.path))
        if os.path.isdir(path):
            os.chdir(path)
            if (len(os.path.abspath(os.path.curdir)) >= len(root_path)):
                self.request.send(protocol.Protocol.json_cd(os.path.curdir, status="200").encode())
            else:  # 用户文件根目录的上层目录
                os.chdir(old_path)
                self.request.send(protocol.Protocol.json_cd(os.path.curdir, status="403").encode())  # 返回状态码403
        else:  # 不是目录
            self.request.send(protocol.Protocol.json_cd(os.path.curdir, status="404").encode())

    def ls(self, *args):  # 显示当前目录文件
        cmd_dic = args[0]
        cmd = cmd_dic["cmd"]
        result = os.popen(cmd).read()
        self.request.send(protocol.Protocol.json_ls(cmd="", result=result).encode())

    def put(self, *args):  # 接收客户端上传的文件
        cmd_dic = args[0]
        filename = cmd_dic["filename"]
        filesize = cmd_dic["filesize"]
        if self.available < filesize:  # 空间不足
            self.request.send(protocol.Protocol.json_put(None, None, "300").encode())
        else:
            if os.path.isfile(filename):  # 文件存在，先加再减
                self.available = self.available + os.path.getsize(filename) - filesize
            else:  # 文件不存在，直接减去
                self.available -= filesize

            f = open(filename, "wb")
            self.request.send(
                protocol.Protocol.json_put(filename, filesize, "200", total=self.total,
                                           available=self.available).encode())
            received_size = 0  # 以获取的文件大小
            while received_size < filesize:  # 逐行写入文件
                data = self.request.recv(1024)
                f.write(data)
                received_size += len(data)
            print(datetime.datetime.now(), file=LOG_FILE, end="\t")
            print("文件 [%s] 上传完毕" % filename, file=LOG_FILE)
        update.update_available(self.user_file, self.available)  # 更新用户可用剩余空间


def get(self, *args):  # 向客户端发送文件
    cmd_dic = args[0]
    filename = cmd_dic["filename"]
    if os.path.isfile(filename):  # 文件存在
        filesize = os.path.getsize(filename)
        self.request.send(protocol.Protocol.json_get(filename, filesize, status="200").encode())  # 服务器确认连接
        client_response = json.loads(self.request.recv(1024).decode())  # 接受客户端返回的数据
        status = client_response["status"]  # 获取客户端状态码
        if status == "200":  # 客户端正常
            with open(filename, "rb") as f:
                for line in f:
                    self.request.send(line)  # 服务器逐行发送数据
                print(datetime.datetime.now(), file=LOG_FILE, end="\t")
            print("文件 [%s] 发送完毕" % filename, file=LOG_FILE)
    else:
        self.request.send(protocol.Protocol.json_get(None, None, status="404").encode())  # 服务器返回数据
