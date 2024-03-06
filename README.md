# m3u8_downloader
A program that downloads a video according to the m3u8 file address.

## Installation
```shell
pip install -r requirements.txt
```

## Usage
```shell
python downloader.py
```
根据提示输入`m3u8`文件地址，可以采用默认文件名或自己指定。

下载后的视频文件在当前目录下的`video`文件夹中，输出格式为`mp4`。

如果下载过程中出现问题，可以再次执行，程序会自动跳过已下载的文件，以节约带宽消耗。但重新下载时**需要保证`m3u8`文件地址以及文件名和之前的一致!**


## Requirements
- [ffmpeg](https://ffmpeg.org/download.html)

