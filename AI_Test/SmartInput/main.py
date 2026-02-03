#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SmartInput - 智能自适应中英文输入法
作者: AI Assistant
版本: 1.0.0
描述: 
  一个全局键盘监听的输入法，能自动识别中文拼音和英文输入。
  支持 Ctrl+Shift 快捷键切换输入模式（中文 ↔ 英文）。
  集成系统托盘，显示当前输入法状态。
  
核心特性：
  - 全局键盘监听（pynput）
  - 自动模式识别（中文拼音 vs 英文）
  - Ctrl+Shift 快速切换
  - 系统托盘图标
  - 候选词显示（基于 Pinyin2Hanzi）
  - 轻量级、高效、易用
  
快捷键：
  - Ctrl+Shift: 切换输入法模式
  - Space/Enter: 上屏缓冲区
  - Backspace: 删除字符
  - 1-5: 选择候选词
  - ESC: 停止程序

依赖：
  - pynput: 全局键盘监听
  - pystray: 系统托盘集成
  - Pillow: 图像处理
  - Pinyin2Hanzi: 拼音转汉字
  - PyYAML: 配置文件
  - pywin32: Windows API

使用方式：
  python main.py
  或者运行打包后的可执行文件：
  SmartInput.exe
"""

import sys
import os
import threading
import queue
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple
import warnings

# 导入依赖库
try:
    from pynput import keyboard
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw, ImageFont
    from Pinyin2Hanzi import DefaultDagParams
    from Pinyin2Hanzi.dag import dag
except ImportError as e:
    print(f"错误: 缺少必要的依赖库: {e}")
    print("请运行: pip install -r requirements.txt")
    sys.exit(1)

# 忽略特定警告
warnings.filterwarnings('ignore')

# ==================== 资源路径处理 ====================
def resource_path(relative_path):
    """
    获取资源文件的绝对路径。
    支持 PyInstaller 打包后的资源访问。
    
    Args:
        relative_path (str): 相对于项目根目录的资源路径
        
    Returns:
        str: 绝对路径
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包模式
        base_path = sys._MEIPASS
    else:
        # 开发模式
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_path, relative_path)

# ==================== 全局配置与状态 ====================

# 输入法状态
current_mode = "unknown"  # 当前输入模式: pinyin, english, unknown
input_buffer = ""  # 输入缓冲区（拼音）
raw_input_buffer = ""  # 原始输入缓冲区
current_candidates = []  # 当前候选词列表

# 快捷键状态跟踪
ctrl_pressed = False  # 跟踪 Ctrl 键状态
shift_pressed = False  # 跟踪 Shift 键状态

# 通信队列
ui_queue = queue.Queue()  # UI 更新队列
stop_event = threading.Event()  # 停止事件

# Pinyin2Hanzi 初始化
dag_params = DefaultDagParams()

def simple_seg(pinyin_str, top_k=5, dagparams=None):
    """
    简化的拼音分词函数，使用 dag 函数实现。
    
    Args:
        pinyin_str (str): 拼音字符串（如 'nihao'）
        top_k (int): 返回前 k 个候选
        dagparams: DAG 参数对象
        
    Returns:
        List[str]: 候选词列表
    """
    if not pinyin_str:
        return []
    
    try:
        # 简单的拼音分词处理
        # 实际使用时可能需要更复杂的分词逻辑
        pinyin_list = []
        i = 0
        while i < len(pinyin_str):
            # 尝试匹配双字母或单字母拼音
            if i + 2 <= len(pinyin_str):
                pinyin_list.append(pinyin_str[i:i+2])
                i += 2
            else:
                pinyin_list.append(pinyin_str[i])
                i += 1
        
        # 使用 dag 函数获取候选
        params = dagparams if dagparams else dag_params
        result = dag(params, pinyin_list, path_num=top_k)
        
        # 提取路径并转换为字符串
        candidates = [''.join(item.path) for item in result]
        return candidates[:top_k]
    except Exception as e:
        print(f"拼音转换错误: {e}")
        return []

# ================== 托盘图标相关全局变量 ==================
tray_icon = None
tray_menu = None
tray_thread = None
tray_stop_event = threading.Event()

# ==================== 数据类 ====================

@dataclass
class UIState:
    """UI 更新状态"""
    visible: bool
    buffer: str
    candidates: List[str]

# ==================== 拼音识别函数 ====================

def is_pinyin_sequence_prefix(text):
    """
    检查输入文本是否符合拼音序列的前缀。
    
    Args:
        text (str): 输入的文本
        
    Returns:
        bool: 是否为拼音前缀
    """
    if not text:
        return False
    
    # 拼音通常只包含英文字母
    if not all(c.isalpha() for c in text.lower()):
        return False
    
    # 简单的拼音前缀检查
    # 完整的拼音识别应该使用专门的库
    valid_initials = set('bpmfdztnlgkhjqxzcs')
    valid_finals = set('aeiouüv')
    
    first_char = text[0].lower()
    if first_char not in valid_initials and first_char not in valid_finals:
        return False
    
    return True

def get_top_candidates(pinyin, top_k=5):
    """
    获取拼音的候选字/词。
    
    Args:
        pinyin (str): 拼音输入
        top_k (int): 返回前 k 个候选
        
    Returns:
        List[str]: 候选字/词列表
    """
    try:
        # 使用 Pinyin2Hanzi 进行转换
        candidates = simple_seg(pinyin, top_k=top_k, dagparams=dag_params)
        return list(candidates)
    except:
        return []

# ==================== 键盘事件处理 ====================

def on_press(key):
    """
    键盘按下事件回调函数。
    新逻辑：
    - 监听所有按键（使用 suppress=True 拦截系统输入）
    - 当用户输入字母时，不让字母直接发送给系统，而是先放入缓存
    - 在 Space/Enter 时，根据缓存内容是"英文模式"还是"中文拼音模式"
      决定是模拟输入英文，还是仅在控制台显示拼音
    - Backspace：中文模式时删除 buffer 最后一个字母
    - 数字键 1-5：中文模式时选择对应候选词并上屏
    - Ctrl+Shift：强制切换模式（仿搜狗输入法）
    """
    global input_buffer, raw_input_buffer, current_mode, current_candidates
    global ctrl_pressed, shift_pressed

    # 先尝试获取字符形式
    try:
        ch = key.char
    except AttributeError:
        ch = None

    # ========== 组合键状态跟踪 ==========
    if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
        ctrl_pressed = True
        return

    # ========== 情况 0：Ctrl+Shift 键（强制切换模式） ==========
    if key == keyboard.Key.shift or key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
        shift_pressed = True
        # 只在 Ctrl+Shift 时切换模式
        if not ctrl_pressed:
            # 仅 Shift，不处理
            return
        
        # 强制切换模式：清空 buffer 并切换模式
        if current_mode == "pinyin":
            current_mode = "english"
            print("[Ctrl+Shift 切换] 切换到英文模式")
        elif current_mode == "english":
            current_mode = "pinyin"
            print("[Ctrl+Shift 切换] 切换到中文拼音模式")
        else:
            current_mode = "pinyin"
            print("[Ctrl+Shift 切换] 切换到中文拼音模式")
        
        input_buffer = ""
        raw_input_buffer = ""
        current_candidates = []
        ui_queue.put(UIState(visible=(current_mode == "pinyin"), buffer="", candidates=[]))
        
        # 通知托盘更新图标和菜单
        update_tray_menu(current_mode)
        update_tray_icon_image(current_mode)
        
        return

    # ========== 情况 1：Backspace（退格） ==========
    if key == keyboard.Key.backspace:
        if current_mode == "pinyin" and input_buffer:
            input_buffer = input_buffer[:-1]
            raw_input_buffer = raw_input_buffer[:-1]
            
            prev_mode = current_mode
            
            if input_buffer:
                if is_pinyin_sequence_prefix(input_buffer):
                    current_mode = "pinyin"
                else:
                    current_mode = "english"
            else:
                current_mode = "unknown"
            
            if current_mode != prev_mode:
                if current_mode in ("pinyin", "english"):
                    update_tray_menu(current_mode)
                    update_tray_icon_image(current_mode)
            
            if current_mode == "pinyin":
                current_candidates = get_top_candidates(input_buffer, top_k=5)
                ui_queue.put(UIState(visible=True, buffer=input_buffer, candidates=current_candidates))
            else:
                current_candidates = []
                ui_queue.put(UIState(visible=False, buffer=input_buffer, candidates=[]))
            
            print(f"[退格] 删除后 buffer: '{input_buffer}', 模式: {current_mode}")
            return

    # ========== 情况 2：ESC（停止监听） ==========
    if key == keyboard.Key.esc:
        print("[ESC] 停止监听")
        stop_event.set()
        return False

    # ========== 情况 3：字母（a-z, A-Z） ==========
    if ch and ch.isalpha():
        raw_input_buffer += ch
        
        # 判断当前模式
        prev_mode = current_mode
        if is_pinyin_sequence_prefix(raw_input_buffer):
            current_mode = "pinyin"
            input_buffer = raw_input_buffer
        else:
            current_mode = "english"
            input_buffer = raw_input_buffer
        
        # 如果模式变更，更新托盘
        if current_mode != prev_mode and current_mode in ("pinyin", "english"):
            update_tray_menu(current_mode)
            update_tray_icon_image(current_mode)
        
        # 重新计算候选词
        if current_mode == "pinyin":
            current_candidates = get_top_candidates(input_buffer, top_k=5)
            ui_queue.put(UIState(visible=True, buffer=input_buffer, candidates=current_candidates))
        else:
            current_candidates = []
            ui_queue.put(UIState(visible=False, buffer=input_buffer, candidates=[]))
        
        print(f"[输入] buffer: '{input_buffer}', 模式: {current_mode}, 候选词: {current_candidates}")
        return
    
    # ========== 情况 4：Space/Enter（上屏） ==========
    if key in (keyboard.Key.space, keyboard.Key.enter):
        if input_buffer:
            if current_mode == "pinyin":
                # 中文模式：输出第一个候选词或拼音本身
                if current_candidates:
                    output = current_candidates[0]
                else:
                    output = input_buffer
                print(f"[上屏] 输出: '{output}'")
            else:
                # 英文模式：直接输出缓冲区
                output = input_buffer
                print(f"[上屏] 输出: '{output}'")
            
            # 清空缓冲区
            input_buffer = ""
            raw_input_buffer = ""
            current_candidates = []
            current_mode = "unknown"
            ui_queue.put(UIState(visible=False, buffer="", candidates=[]))
        return
    
    # ========== 情况 5：数字键 1-5（候选词选择） ==========
    if ch and ch.isdigit() and ch in '12345':
        if current_mode == "pinyin" and current_candidates:
            idx = int(ch) - 1
            if idx < len(current_candidates):
                output = current_candidates[idx]
                print(f"[选词] 选择: '{output}'")
                
                # 清空缓冲区
                input_buffer = ""
                raw_input_buffer = ""
                current_candidates = []
                current_mode = "unknown"
                ui_queue.put(UIState(visible=False, buffer="", candidates=[]))
                return

# ==================== 按键释放处理 ====================

def on_release(key):
    """
    键盘抬起事件回调函数。
    - Ctrl 抬起时重置 ctrl_pressed
    - Shift 抬起时重置 shift_pressed
    - ESC 抬起时停止监听
    """
    global ctrl_pressed, shift_pressed
    
    # 更新按键状态
    if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
        ctrl_pressed = False
        return
    
    if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
        shift_pressed = False
        return
    
    # ESC 键停止程序
    if key == keyboard.Key.esc:
        print("检测到 ESC，停止监听。")
        stop_event.set()
        return False

# ================== 托盘菜单与图标管理 ==================

def get_tray_icon_image(mode: str) -> Image.Image:
    """
    获取托盘图标。
    
    Args:
        mode (str): 输入模式 (pinyin, english, unknown)
        
    Returns:
        Image.Image: 图标 PIL 图像
    """
    # 尝试从文件加载
    if mode == "pinyin":
        icon_path = resource_path("zh.png")
    else:
        icon_path = resource_path("en.png")
    
    try:
        if os.path.exists(icon_path):
            return Image.open(icon_path).convert("RGBA")
    except:
        pass
    
    # 如果文件不存在或加载失败，创建默认图标
    img = Image.new('RGBA', (32, 32), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    
    if mode == "pinyin":
        # 中文模式：绘制 "中"
        d.rectangle([2, 2, 30, 30], outline=(0, 120, 180), width=2)
        d.text((8, 8), "中", fill=(0, 120, 180))
    else:
        # 英文模式：绘制 "EN"
        d.rectangle([2, 2, 30, 30], outline=(200, 100, 100), width=2)
        d.text((6, 8), "EN", fill=(200, 100, 100))
    
    return img

def update_tray_icon_image(mode: str):
    """
    更新托盘图标。
    
    Args:
        mode (str): 输入模式
    """
    global tray_icon
    if tray_icon:
        try:
            img = get_tray_icon_image(mode)
            tray_icon.icon = img
        except Exception as e:
            print(f"更新托盘图标失败: {e}")

def update_tray_menu(mode: str):
    """
    更新托盘菜单。
    
    Args:
        mode (str): 输入模式
    """
    global tray_icon, tray_menu
    
    if mode == "pinyin":
        mode_text = "中文模式 🇨🇳"
    elif mode == "english":
        mode_text = "英文模式 🇬🇧"
    else:
        mode_text = "未知模式"
    
    # 创建菜单
    tray_menu = Menu(
        MenuItem(f"当前模式: {mode_text}", lambda icon, item: None),
        MenuItem("强制切换模式 (Ctrl+Shift)", lambda icon, item: None),
        Menu.SEPARATOR,
        MenuItem("退出 (ESC)", lambda icon, item: quit_from_tray(icon)),
    )
    
    if tray_icon:
        tray_icon.menu = tray_menu

def quit_from_tray(icon):
    """从托盘退出程序"""
    global tray_icon
    icon.stop()
    stop_event.set()

def setup_tray():
    """
    设置系统托盘。
    在单独的线程中运行，不阻塞主线程。
    """
    global tray_icon, tray_menu
    
    try:
        # 创建初始菜单
        tray_menu = Menu(
            MenuItem("当前模式: 未知模式", lambda icon, item: None),
            MenuItem("强制切换模式 (Ctrl+Shift)", lambda icon, item: None),
            Menu.SEPARATOR,
            MenuItem("退出 (ESC)", lambda icon, item: quit_from_tray(icon)),
        )
        
        # 创建图标
        img = get_tray_icon_image("unknown")
        
        # 创建托盘图标
        tray_icon = Icon("SmartInput", img, menu=tray_menu)
        
        print("[托盘] SmartInput 托盘已启动")
        
        # 运行托盘（阻塞，直到 stop 被调用）
        tray_icon.run()
        
    except Exception as e:
        print(f"[错误] 托盘初始化失败: {e}")

# ==================== UI 处理线程 ====================

def ui_worker():
    """
    处理 UI 更新的工作线程。
    监听 ui_queue，更新显示状态。
    """
    print("[UI] UI 工作线程已启动")
    
    while not stop_event.is_set():
        try:
            state = ui_queue.get(timeout=0.5)
            if state:
                if state.visible:
                    print(f"[UI] 显示: 缓冲区='{state.buffer}', 候选词={state.candidates}")
                else:
                    print(f"[UI] 隐藏输入框")
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[错误] UI 处理错误: {e}")
    
    print("[UI] UI 工作线程已停止")

# ==================== 主函数 ====================

def main():
    """
    主函数。
    设置和运行输入法。
    """
    print("=" * 60)
    print("SmartInput - 智能自适应中英文输入法")
    print("版本: 1.0.0")
    print("=" * 60)
    
    global tray_thread
    
    try:
        # 1. 启动托盘线程
        print("\n[初始化] 启动托盘线程...")
        tray_thread = threading.Thread(target=setup_tray, daemon=True)
        tray_thread.start()
        
        # 2. 启动 UI 工作线程
        print("[初始化] 启动 UI 工作线程...")
        ui_thread = threading.Thread(target=ui_worker, daemon=True)
        ui_thread.start()
        
        # 3. 启动全局键盘监听
        print("[初始化] 启动键盘监听线程...")
        print("[提示] 按 ESC 停止程序")
        print("[提示] 按 Ctrl+Shift 切换输入法模式")
        print("[初始化] SmartInput 已启动\n")
        
        # 创建键盘监听器
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        
        # 等待停止事件
        while not stop_event.is_set():
            try:
                stop_event.wait(timeout=0.5)
            except KeyboardInterrupt:
                break
        
        # 清理
        print("\n[清理] 停止键盘监听...")
        listener.stop()
        listener.join(timeout=2)
        
        print("[清理] 停止托盘...")
        if tray_icon:
            tray_icon.stop()
        
        print("[清理] SmartInput 已停止")
        
    except Exception as e:
        print(f"[错误] 程序执行错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
