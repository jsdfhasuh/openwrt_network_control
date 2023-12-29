import asyncio
import json
import subprocess
import time
import re
import ipaddress

def extract_number_and_unit(s):
    # 定义正则表达式
    pattern = r'([\d.]+)([A-Za-z]+)'

    # 使用正则表达式匹配字符串
    match = re.match(pattern, s)

    # 如果匹配成功，提取数字和单位
    if match:
        number = float(match.group(1))
        unit = match.group(2)
        return number, unit
    else:
        return None

def is_ip_in_network(ip_str, network_str):
    ip = ipaddress.IPv4Address(ip_str)
    network = ipaddress.IPv4Network(network_str, strict=False)  # strict=False允许IP与网络的边界重叠
    return ip in network

def speed_change(raw_speed):
    number, unit = extract_number_and_unit(raw_speed)
    # 先转换到Kb
    if 'b' == unit:
        number = number / 1024
    if 'Kb' == unit:
        pass
    elif 'Mb' == unit:
        number = 1024*number
    elif 'Gb' == unit:
        number = 1024*1024*number
    speed = str(number * 0.125) + 'KB/s'
    return speed

def cumulative_change(raw_cumulative):
    number, unit = extract_number_and_unit(raw_cumulative)
    if number == 0:
        pass
    if 'B' == unit:
        number = number / 1024 / 1024
    if 'KB' == unit:
        number = number / 1024
    elif 'MB' == unit:
        pass
    elif 'GB' == unit:
        number = 1024*number
    cumulative = str(number) + 'MB'
    return cumulative

def get_info(raw_data):
    # 使用正则表达式匹配并提取值

    match = re.match(r'\s*\d* +(\d+\.\d+\.\d+\.\d+):*\d*\s+(=>|<=)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', raw_data)
    if match:
        ip, flow,in_2s, in_10s, in_40s, cumulative = match.groups()
        in_2s =speed_change(in_2s)
        in_10s = speed_change(in_10s)
        in_40s = speed_change(in_40s)
        cumulative = cumulative_change(raw_cumulative=cumulative)

        # 打印提取的值
        #print(f"Source: {source}")
        #print(f"In 2s: {in_2s}")
        #print(f"In 10s: {in_10s}")
        #print(f"In 40s: {in_40s}")
        #print(f"Cumulative: {cumulative}")
        return ip,flow, in_2s, in_10s, in_40s, cumulative

def add_unit(parm1,parm2): #带单位的加法
    number1,unit1 = extract_number_and_unit(parm1)
    number2,unit2 = extract_number_and_unit(parm2)
    if number2 == 0 or number1 == 0:
        pass
    if unit1 == unit2:
        pass
    else:
        pass
        raise ValueError
    new_number = number2+number1
    result = str(new_number) + unit1
    return result
async def get_iftop():
    try:
        result = subprocess.run(['iftop', '-i', 'br-lan', '-n', '-t', '-L', '3000', '-s', '30'],capture_output=True, text=True, check=True)
        return result
    except subprocess.CalledProcessError as e:
        # 如果命令执行失败，捕获异常并输出错误信息
        print(f"Error: {e}")


async def consume(queue):
    while True:
        # 从队列中获取输出
        raw_data = await queue.get()
        extra_info_line = []
        main_info_line = []
        network_to_check = "192.168.1.0/24"
        change = 0
        flag = False
        for line in raw_data.splitlines():
            if "-----------------" in line and change < 2:
                flag = not flag
                change += 1
                continue
            if not flag:
                extra_info_line.append(line)
            else:
                main_info_line.append(line)
        paired_array = []
        main_info = []
        target_info = {}
        all_up = 0
        all_dl = 0
        for i in range(0, len(main_info_line), 2):
            # 取出两个元素
            element1 = main_info_line[i]
            element2 = main_info_line[i + 1] if i + 1 < len(main_info_line) else None
            try:
                ip, _, _, _, _, _ = get_info(raw_data=element1)
            except Exception as e:
                pass
            try:
                if is_ip_in_network(ip, network_to_check):  # =>指向就说明数据流向
                    #print(f'为内部IP部分')
                    outip, _, last2_dlspeed, last4_dlspeed, last10_dlspeed, all_re = get_info(
                        raw_data=element2)  # 外部IP,前2s下载速度平均，前4s下载速度平均，前10s下载速度平均
                    inip, _, last2_upspeed, last4_upspeed, last10_upspeed, all_ta = get_info(
                        raw_data=element1)  # 内部IP,前2s上传速度平均，前4s上传速度平均，前10s上传速度平均
                else:
                    #print(f'为外部IP部分')
                    outip, _, last2_dlspeed, last4_dlspeed, last10_dlspeed, all_re = get_info(
                        raw_data=element1)  # 外部IP,前2s下载速度平均，前4s下载速度平均，前10s下载速度平均
                    inip, _, last2_upspeed, last4_upspeed, last10_upspeed, all_ta = get_info(
                        raw_data=element2)  # 内部IP,前2s上传速度平均，前4s上传速度平均，前10s上传速度平均
                if inip not in target_info:
                    target_info[inip] = {'downloads_speed': last2_dlspeed, 'up_speed': last2_upspeed,
                                         'cumulative': {'download': all_ta, 'upload': all_re}, "connenct_ip": [outip]}
                else:
                    pass
                    target_info[inip]['downloads_speed'] = add_unit(target_info[inip]['downloads_speed'], last2_dlspeed)
                    target_info[inip]['up_speed'] = add_unit(target_info[inip]['up_speed'], last2_upspeed)
                    target_info[inip]['cumulative']['download'] = add_unit(target_info[inip]['cumulative']['download'],
                                                                           all_ta)
                    target_info[inip]['cumulative']['upload'] = add_unit(target_info[inip]['cumulative']['upload'],
                                                                         all_re)
                    target_info[inip]['connenct_ip'].append(outip)
                    pass
                # 将两个元素组合成新的一组，并添加到新数组中
            except Exception as e:
                pass
        pass
        with open(file='result.json',mode='w') as f:
            json.dump(target_info,f,indent=4)
        print('处理完数据')
        # 在这里添加你对输出的处理逻辑

async def produce(queue):
    while True:
        print('开始抓取数据')
        loop = asyncio.get_event_loop()
        task = loop.create_task(get_iftop())
        await asyncio.wait_for(task, None)
        result = task.result()
        # 将iftop的输出放入队列
        await queue.put(result.stdout)

async def main():
    # 创建一个异步队列
    queue = asyncio.Queue()

    # 启动生产者和消费者任务
    producer_task = asyncio.create_task(produce(queue))
    consumer_task = asyncio.create_task(consume(queue))

    # 等待两个任务完成
    await asyncio.gather(producer_task, consumer_task)

if __name__ == "__main__":
    asyncio.run(main())