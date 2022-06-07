import socket
import os
import json

import sys

from src import protocol

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FTPClient(object):
    def __init__(self, ip, port):  # 设定地址和端口
        self.client = socket.socket()
        self.ip = ip
        self.port = port
        self.total = 0
        self.available = 0

    def __connect(self, ip, port):  # 客户端连接服务端
        self.client.connect((ip, port))

    def __auth(self):  # 客户端认证
        account = input("请输入用户名>>:").strip()
        password = input("请输入密码>>:").strip()
        self.client.send(protocol.Protocol.json_auth(account, password).encode())  # 客户端发送请求
        server_response = json.loads(self.client.recv(1024).decode())  # 接受服务器返回的数据
        status = server_response["status"]  # 获取状态码
        if status == "200":  # 验证成功
            self.total = server_response["total"]  # 设置登录用户的信息并显示
            self.available = server_response["available"]
            self.path = "%s/data/downloads" % BASE_DIR
            print("总大小为: \t%.2f MB" % (self.total / 2 ** 20))
            print("可用空间为: \t%.2f MB" % (self.available / 2 ** 20))
        else:  # 验证失败
            print("用户名或密码错误!")
            self.cmd_exit()

    def __interactive(self):  # 交互
        while True:  # while True
            cmd = input("请输入指令>>:").strip()
            # strip() 方法用于移除字符串头尾指定的字符(默认为空格或换行符)或字符序列。注意:该方法只能删除开头或是结尾的字符,不能删除中间部分的字符。
            if len(cmd) == 0:
                continue
            cmd_str = cmd.split()[0]
            if hasattr(self, "cmd_%s" % cmd_str):
                func = getattr(self, "cmd_%s" % cmd_str)
                func(cmd)
            else:
                self.cmd_help()

    def start(self, *args):  # 开启客户端
        self.__connect(self.ip, self.port)
        self.__auth()
        self.__interactive()

    @staticmethod
    def cmd_help():  # 显示帮助
        # ok
        msg = """
        ------------可用命令------------
        ls              列出当前目录下文件
        pwd             显示当前文件路径
        cd              进入指定目录
        get filename    下载指定文件
        put filename    上传指定文件
        mkdir dirname   创建目录
        rm filename     删除指定文件/目录
        exit            退出
        """
        print(msg)

    def cmd_rm(self, *args):  # 删除指定文件
        # ok
        cmd_split = args[0].split()
        if len(cmd_split) > 1:
            filename = cmd_split[1]  # 获取文件名
            self.client.send(protocol.Protocol.json_rm(filename).encode())  # 客户端发送请求
            res_rm = json.loads(self.client.recv(1024).decode())  # 接受服务器返回的数据
            status = res_rm["status"]  # 获取状态码
            if status == "404":
                print("文件不存在!")
            elif status == "200":  # 删除成功
                self.total = res_rm["total"]
                self.available = res_rm["available"]
                print("文件删除成功")
                print("总大小为: \t%.2f MB" % (self.total / 2 ** 20))
                print("可用空间为: \t%.2f MB" % (self.available / 2 ** 20))
        else:
            print("请输入需要删除的文件名")

    def cmd_mkdir(self, *args):  # 创建目录
        # ok
        cmd = args[0]
        cmd_split = cmd.split()
        if len(cmd_split) > 1:
            self.client.send(protocol.Protocol.json_mkdir(cmd).encode())
            res_mkdir = json.loads(self.client.recv(1024).decode())  # 接受服务器返回的数据
            status = res_mkdir["status"]  # 获取状态码
            if status == "404":
                print("文件夹已经存在!")
            elif status == "200":  # 新建成功
                print("新建文件夹成功")
        else:
            print("请输入文件夹名称")

    def cmd_cd(self, *args):  # 进入指定目录
        # ok
        cmd_split = args[0].split()
        if len(cmd_split) > 1:
            dir_name = cmd_split[1]
            self.client.send(protocol.Protocol.json_cd(dir_name).encode())  # 客户端发送请求
            res_cd = json.loads(self.client.recv(1024).decode())  # 接受服务器返回的数据
            status = res_cd["status"]  # 获取状态码
            if status == "404":
                print("目录不存在!")
            elif status == "403":
                print("不能访问根目录的上层目录!")
        else:
            print("请输入路径")

    def cmd_pwd(self, *args):  # 显示当前目录路径
        # ok
        self.client.send(protocol.Protocol.json_pwd().encode())
        res_pwd = self.client.recv(1024).decode()
        print("当前路径: %s" % res_pwd)

    @staticmethod
    def cmd_exit():  # 退出客户端
        # ok
        exit()

    def cmd_ls(self, *args):  # ls指令：列举当前目录下的文件
        # ok
        cmd = args[0]
        self.client.send(protocol.Protocol.json_ls(cmd=cmd).encode())  # 客户端发送请求
        res_ls = json.loads(self.client.recv(1024).decode())  # 接受服务器返回的数据
        print(res_ls["result"])

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
                status = server_response["status"]  # 获取状态码
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
                            print("总大小为: \t%.2f MB" % (self.total / 2 ** 20))
                            print("可用空间为: \t%.2f MB" % (self.available / 2 ** 20))
                elif status == "300":
                    print("可用空间为: \t%.2f MB" % (self.available / 2 ** 20))
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
            status = server_response["status"]  # 获取状态码
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

    @staticmethod
    def progress(percent, width=50):  # 进度条打印
        if percent >= 100:
            percent = 100
        show_str = ('[%%-%ds]' % width) % (int(width * percent / 100) * "#")  # 字符串拼接的嵌套使用
        print("\r%s %d%%" % (show_str, percent), end='', file=sys.stdout, flush=True)
