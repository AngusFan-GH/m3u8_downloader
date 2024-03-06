import asyncio
import os
import re
import shutil  # 用于删除文件夹及其内容
import time

import aiohttp
import m3u8
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

VIDEO_FOLDER = "video"  # 视频文件夹名称
TEMP_FOLDER = "temp"  # 临时文件夹名称
DOWNLOADED = 0  # 已下载的片段数量


class ProgressTracker:
    def __init__(self, total):
        self.total = total
        self.completed = 0
        self.lock = asyncio.Lock()

    async def update(self):
        async with self.lock:
            self.completed += 1
            self.print_progress()

    def print_progress(self):
        percent = (self.completed / self.total) * 100
        bar_length = 40
        block = int(round(bar_length * self.completed / self.total))
        text = f"\rProgress: [{'#' * block + '-' * (bar_length - block)}] {percent:.2f}% ({self.completed}/{self.total})"
        print(text, end="", flush=True)


def make_absolute_url(base_url, relative_url):
    from urllib.parse import urljoin
    return urljoin(base_url, relative_url)


async def download_and_decrypt_segment(session, cipher, segment_uri, segment_index, tracker, folder):
    segment_path = os.path.join(folder, f"segment_{segment_index}.ts")
    # 如果文件已存在，则跳过下载
    if os.path.exists(segment_path):
        print(f"Segment {segment_index} already exists, skipping download.")
        return

    # print(f"Downloading segment: {segment_index}.")
    async with session.get(segment_uri) as response:
        segment_content = await response.read()
        if cipher:  # 如果存在解密器，解密片段
            decryptor = cipher.decryptor()
            segment_content = decryptor.update(
                segment_content) + decryptor.finalize()
        # 保存解密后的片段为文件
        with open(segment_path, 'wb') as f:
            f.write(segment_content)

        await tracker.update()

    # print(f"Segment processed: {segment_index}.")


async def main(m3u8_url, filename=None):
    if not filename:
        match = re.search(r'/([^/]+)\.m3u8', m3u8_url)
        filename = match.group(1)
        if filename == 'index' or filename is None:
            # 如果文件名为index，则使用时间戳作为文件名
            filename = str(int(time.time()))

    cache_folder = f"{TEMP_FOLDER}/{filename}"

    # 确保temp和video文件夹存在
    os.makedirs(cache_folder, exist_ok=True)
    os.makedirs(VIDEO_FOLDER, exist_ok=True)

    SEGMENT_LIST_FILE = os.path.join(cache_folder, "file_list.txt")  # 视频片段列表文件

    print(f"Start handle m3u8 file:{filename}.")
    async with aiohttp.ClientSession() as session:
        async with session.get(m3u8_url) as response:
            m3u8_content = await response.text()

    # 解析M3U8文件
    playlist = m3u8.loads(m3u8_content)
    if playlist.is_variant:  # 如果是主播放列表，选择第一个变体
        base_url = m3u8_url.rsplit('/', 1)[0] + '/'
        variant_url = make_absolute_url(
            base_url, playlist.playlists[0].uri)
        async with aiohttp.ClientSession() as session:
            async with session.get(variant_url) as response:
                variant_content = await response.text()
        playlist = m3u8.loads(variant_content)

    is_encrypted = playlist.keys and playlist.keys[0]  # 检查是否存在加密密钥
    cipher = None

    # 如果存在加密密钥，设置解密器
    if is_encrypted:
        key_uri = playlist.keys[0].uri  # 获取密钥URI
        # 异步下载密钥
        async with aiohttp.ClientSession() as session:
            async with session.get(key_uri) as response:
                key = await response.read()
        # 设置解密器
        cipher = Cipher(algorithms.AES(key), modes.CBC(
            key[:16]), backend=default_backend())
        print("Encrypted video detected, key downloaded.")

    # 准备视频片段列表文件
    with open(SEGMENT_LIST_FILE, 'w') as list_file:
        length = len(playlist.segments)
        for i in range(length):
            segment_path = f"segment_{i}.ts"
            list_file.write(f"file '{segment_path}'\n")

    tracker = ProgressTracker(length)
    print(f"Total segments to download: {length}.")

    # 异步下载并解密视频片段
    tasks = []
    async with aiohttp.ClientSession() as session:
        for i, segment in enumerate(playlist.segments):
            task = download_and_decrypt_segment(
                session, cipher, segment.uri, i, tracker, cache_folder)
            tasks.append(task)
        print("Start download video segments")
        await asyncio.gather(*tasks)

    print("All video segments downloaded, start merge video segments to a file.")
    # 确保输出文件保存在video文件夹中
    output_file = os.path.join(VIDEO_FOLDER, f"{filename}.mp4")
    # 使用ffmpeg合并视频，通过读取视频片段列表文件
    merge_command = f"ffmpeg -f concat -safe 0 -i {SEGMENT_LIST_FILE} -c copy {output_file}"
    if os.system(merge_command) == 0:
        print("Video merged successfully, start cleanup temp files.")
        # 清理temp文件夹
        shutil.rmtree(cache_folder)
        print("Temp files cleaned up.")
    else:
        print("Video merge failed.")

# 运行异步主函数
if __name__ == "__main__":
    m3u8_url = input("Please input the url of m3u8: ")
    if not m3u8_url:
        print("You must input the url of m3u8.")
        m3u8_url = input("Please input the url of m3u8: ")
        if not m3u8_url:
            exit(0)
    # 询问是否需要指定文件名
    filename = input("Do you want to specify the filename? (y/n): ")
    if filename == 'y':
        filename = input("Please input the filename: ")
        # 处理文件名，如果有空格，则替换为下划线
        filename = filename.replace(' ', '_')
    print("Program start...")
    asyncio.run(main(m3u8_url, filename))
    print("Program end.")
