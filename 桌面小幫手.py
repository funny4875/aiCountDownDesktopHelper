分科時間=[2026,7,11]
EXAM_COUNTDOWN_URL = "https://hlmath.tw/exam-countdown/"
EXAM_NAME = "分科能力測驗"
import pyautogui
import pyperclip
import os
from tkinter import *
from tkinter import ttk, messagebox
import webbrowser
import threading
import tkinter.font as font
import keyboard
import pyttsx3
from pytubefix import YouTube
engine = None

from PIL import Image, ImageTk
import time
import requests
import os
#連續語音辨識
import speech_recognition as sr

#google ai
from google import genai
AIclient = None
AI_API_KEY = None
AI_MODEL = None
import re

import datetime
def 更新分科時間():
    global 分科時間
    try:
        response = requests.get(EXAM_COUNTDOWN_URL, timeout=8)
        response.raise_for_status()
        response.encoding = response.encoding or response.apparent_encoding or "utf-8"
        html = response.text
        pattern = rf"\d{{3,4}}{EXAM_NAME}.*?舉辦時間：\s*(\d{{3,4}})-(\d{{1,2}})-(\d{{1,2}})"
        match = re.search(pattern, html, re.S)
        if not match:
            raise ValueError(f"找不到 {EXAM_NAME} 的舉辦時間")

        year, month, day = map(int, match.groups())
        if year < 1911:
            year += 1911
        分科時間 = [year, month, day]
        print(f"已從 {EXAM_COUNTDOWN_URL} 取得{EXAM_NAME}日期：{year}-{month:02d}-{day:02d}")
        return True
    except Exception as e:
        print(f"讀取{EXAM_NAME}日期失敗，沿用預設日期 {分科時間[0]}-{分科時間[1]:02d}-{分科時間[2]:02d}：{e}")
        return False

def countDown(Y,M,D,m,d,s):
    now = datetime.datetime.now()
    target = datetime.datetime(分科時間[0], 分科時間[1], 分科時間[2], 0, 0, 0)
    time_diff = target - now
    days = time_diff.days
    hours, remainder = divmod(time_diff.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return days,hours,minutes,seconds

import pygetwindow as gw
def get_window(title='Roblox'):
    windows = gw.getWindowsWithTitle(title)
    if not windows:
        #print(f"找不到標題為 '{title}' 的視窗。")
        return
    for window in windows:
        if window.title == title:
            width, height = window.width, window.height
            print(f"視窗 '{window.title}' 的大小為: {width}x{height}")
            return window
    return None
isRec = True
def restartRec(event):
    global isRec
    isRec = True
    
import vlc   
#監聽 hotkey : 'p'鍵按下時觸發下列函式
player=None
def play_youtube(keyword):
  global player
  params={"search_query":keyword}
  res=requests.get("https://www.youtube.com/results",params)
  i=res.text.find('/watch?v=',0)
  j=res.text.find('"',i)
  vid=res.text[i:j]
  filename = downloadMP3("https://www.youtube.com"+vid,keyword+'.mp3')
  if player!=None:player.stop()
  player = vlc.MediaPlayer(filename)
  player.play()
#   webbrowser.open_new_tab("https://www.youtube.com"+vid)
def 結束音樂():
    global player,isRec,img_offset
    if not player:return
    isRec=True
    img_offset=0
    player.stop()
def 暫停音樂():
    global player,isRec,img_offset
    if player==None:return
    isRec=True
    img_offset=0
    if player.can_pause():player.pause()
def 繼續音樂():
    global player,isRec,img_offset
    if not player:return
    isRec=False
    img_offset=6
    player.play()
def downloadMP3(url,filename):
    #youtube mp3下載
    cwd=os.path.dirname(os.path.abspath(__file__))
    mp3_dir=os.path.join(cwd,'mp3')
    os.makedirs(mp3_dir,exist_ok=True)
    yt=YouTube(url)
    print('下載中…')
    yt.streams.filter().get_audio_only().download(output_path=mp3_dir,filename=filename)
    filepath=os.path.join(mp3_dir,filename)
    print('已下載至下列位置')
    print(filepath)
    return filepath

def MouseDown(event):
    global moveYN # 是否可以移動視窗的全域變數
    global mousX  # 全域變數，滑鼠在視窗內的 x 座標
    global mousY  # 全域變數，滑鼠在視窗內的 y 座標
    moveYN=True    # 開啟移動視窗的開關
    mousX=event.x  # 取得滑鼠相對於視窗左上角的 X 座標
    mousY=event.y   # 取得滑鼠相對於視窗左上角的 Y 座標
    
def MouseUp(event):moveYN=False   # 关闭移动窗体的开关
la1_offsetX = 500
def MouseMove(event):
    global la1_offsetX
    if moveYN==True: # 如果鼠标按下，就可以移动窗体到新的位置
        root.geometry(f'+{event.x_root - mousX-la1_offsetX}+{event.y_root - mousY}') 
def exit(event):
    root.destroy()  # 退出程序
    
def popup_menu(event):  # 弹出菜单代码
    popup.post(event.x_root,event.y_root) 
 
def model_display_name(model):
    name = getattr(model, "name", str(model))
    display_name = getattr(model, "display_name", "")
    if display_name and display_name != name:
        return f"{name}  ({display_name})"
    return name

def 設定GoogleAI():
    global AIclient, AI_API_KEY, AI_MODEL
    state = {"client": None, "api_key": None, "model": None}
    model_names = []
    model_records = []

    setup_root = Tk()
    setup_root.title("Gemini 模型選擇器")
    setup_root.geometry("620x245")
    setup_root.resizable(False, False)

    main = ttk.Frame(setup_root, padding=18)
    main.pack(fill="both", expand=True)

    ttk.Label(main, text="Gemini API Key").grid(row=0, column=0, sticky="w")

    api_key_entry = ttk.Entry(main, width=58, show="*")
    api_key_entry.grid(row=1, column=0, padx=(0, 8), pady=(6, 14), sticky="ew")

    ttk.Label(main, text="選擇模型").grid(row=2, column=0, sticky="w")

    model_combo = ttk.Combobox(main, width=75, state="readonly")
    model_combo.grid(row=3, column=0, columnspan=2, pady=(6, 14), sticky="ew")

    selected_label = ttk.Label(main, text="尚未選擇模型")
    selected_label.grid(row=4, column=0, columnspan=2, sticky="w")

    button_frame = ttk.Frame(main)
    button_frame.grid(row=5, column=0, columnspan=2, pady=(12, 0), sticky="e")

    def on_model_selected(_event=None):
        selected = model_combo.get()
        if selected:
            selected_label.config(text=f"已選擇：{selected}")

    def load_models():
        api_key = api_key_entry.get().strip()
        if not api_key:
            messagebox.showwarning("缺少 API Key", "請先輸入 API Key")
            return

        load_button.config(state="disabled")
        model_combo.set("正在讀取模型清單...")
        setup_root.update_idletasks()

        try:
            client = genai.Client(api_key=api_key)
            models = list(client.models.list())
        except Exception as exc:
            model_combo.set("")
            messagebox.showerror("讀取失敗", f"無法取得模型清單：\n{exc}")
            return
        finally:
            load_button.config(state="normal")

        if not models:
            model_combo.set("")
            messagebox.showinfo("沒有模型", "這個 API Key 目前沒有可用模型。")
            return

        state["client"] = client
        state["api_key"] = api_key
        model_names.clear()
        model_names.extend(model_display_name(model) for model in models)
        model_records.clear()
        model_records.extend(models)

        model_combo["values"] = model_names
        model_combo.current(0)
        selected_label.config(text=f"已選擇：{model_names[0]}")

    def confirm():
        index = model_combo.current()
        if index < 0:
            messagebox.showwarning("尚未選擇模型", "請先讀取並選擇模型。")
            return

        model_name = getattr(model_records[index], "name", model_names[index])
        state["model"] = model_name.removeprefix("models/")
        setup_root.destroy()

    def cancel():
        setup_root.destroy()

    load_button = ttk.Button(main, text="讀取模型清單", command=load_models)
    load_button.grid(row=1, column=1, pady=(6, 14), sticky="ew")

    model_combo.bind("<<ComboboxSelected>>", on_model_selected)
    confirm_button = ttk.Button(button_frame, text="確定使用", command=confirm)
    confirm_button.pack(side="right")
    ttk.Button(button_frame, text="取消", command=cancel).pack(side="right", padx=(0, 8))

    main.columnconfigure(0, weight=1)
    setup_root.protocol("WM_DELETE_WINDOW", cancel)
    api_key_entry.focus_set()
    setup_root.mainloop()

    if not state["client"] or not state["model"]:
        return False

    AIclient = state["client"]
    AI_API_KEY = state["api_key"]
    AI_MODEL = state["model"]
    return True

if not 設定GoogleAI():
    raise SystemExit

更新分科時間()

engine = pyttsx3.init()
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[0].id)

root=Tk()  # 主視窗件
root.withdraw()  # 让窗体隐藏一下
root.wm_attributes('-topmost',1)  # 让窗体置顶
 
imgs=[]
img_offset=0
for i in range(8):
    image = Image.open(f'{i}.png')
    new_width = int(image.width * 0.5)
    new_height = int(image.height * 0.5)
    image = image.resize((new_width, new_height), Image.LANCZOS)
    tk_image = ImageTk.PhotoImage(image)
    imgs.append(tk_image)

la1=Label(root, image=imgs[1],bd=0)
la1.place(x=la1_offsetX,y=0) # 用place定位
#la1.bind("<Double-Button-1>",exit) # 鼠标双击标签绑定exit函数

    
la1.bind("<Double-Button-1>",restartRec)
la1.bind("<Button-1>",MouseDown) # 鼠标按下绑定函数，决定可以移动窗体
la1.bind("<ButtonRelease-1>",MouseUp) # 鼠标抬起绑定函数，决定不能移动窗体
la1.bind("<B1-Motion>",MouseMove) # 鼠标按下并移动绑定函数，决定窗体移动到新的位置   
ii=0
la2=Label(root, text="",bd=0,bg="#FFFAFA")
la2.place(x=200,y=0) #用place定位

la3=Label(root, text="分科倒數:\n",bg="red",bd=1,fg="#FFFFFE",font=("Arial", 30))
la3.place(x=220,y=180) #用place定位

root.overrideredirect(True) # 让窗体无标题栏
root.wm_attributes("-transparentcolor", "#FFFFFF") # 设置窗体白色透明

def Time1():
    days,hours,minutes,seconds = countDown(分科時間[0],分科時間[1],分科時間[2],0,0,0)
    T=f"分科倒數：          \n{days}天{hours}時{minutes}分{seconds}秒"
    la3.configure(text=T,bg="#FF0000")    
    root.update()
    la3.after(1000,Time1)
    
def Time2():#每隔5秒眨一次眼
    global ii,img_offset
    ii+=1
    if ii%2==0:
        la1.configure(image=imgs[img_offset])
        la1.after(5000,Time2)
    else:
        la1.configure(image=imgs[img_offset+1])
        la1.after(500,Time2)
        
Time1()        
Time2()        

I=0
lines=[]
with open('勵志小語.txt',encoding='utf8') as f:
    lines=f.readlines()
def 勵志小語():
    global I,lines
    textReply(lines[I]);I+=1

聲音=0
def 切換聲音():
    global 聲音,engine
    print(聲音)
    voices = engine.getProperty('voices')
    聲音=(聲音+1)%len(voices)
    engine.setProperty('voice', voices[聲音].id)
    textReply('切換聲音...')
    
popup=Menu(root,tearoff=0, font=("微軟正黑體", 20,"bold")) # 为弹出菜单创建菜单popup
popup.add_command(label='退出',command=root.destroy) # 退出菜单项也可以退出程序
popup.add_command(label='勵志小語',command=勵志小語) # 退出菜单项也可以退出程序
popup.add_command(label='切換聲音',command=切換聲音)
popup.add_command(label='暫停音樂',command=暫停音樂)
popup.add_command(label='繼續音樂',command=繼續音樂)
popup.add_command(label='結束音樂',command=結束音樂)
root.bind("<Button-3>",popup_menu) # 窗体鼠标右键绑定弹出菜单函数


def textOn(T):
    la2.configure(text=T,font=font.Font(size=30),bg="#FFF8FF")    
    root.update()
    
def textReply(T,delay=0.5):#回應文字
    global ii,img_offset,isRec
    img_offset = 2
    ii+=1
    la1.configure(image=imgs[img_offset+ii%2])
    textOn(T)
    isRec=False
    engine.say(T)
    engine.runAndWait()
    engine.stop()
    time.sleep(delay)
    textOn('')
    img_offset=0
    isRec=True
    
def textReplyLong(T,delay=0.5):#回應文字
    sentences=re.split("[!！?？。\n]+",T)
    for sentence in sentences:
        textReply(sentence,delay)

def GoogleAI產生文字(question):
    response = AIclient.models.generate_content(
        model=AI_MODEL,
        contents=question + "(30字以內)",
    )
    return response.text.strip()
        
def move(dx,dy):
    w = root.winfo_width()
    h = root.winfo_height()
    x = root.winfo_x()+dx
    y = root.winfo_y()+dy
    root.geometry(f'{w}x{h}+{x}+{y}')
    root.update()
    
root.update()
a=la1.winfo_width()+la1_offsetX
b=la1.winfo_height()+50
c=root.winfo_screenwidth()-a
d=root.winfo_screenheight()-b
root.geometry(f'{a}x{b}+{c}+{d}')  
root.configure(bg="#FFFFFF")
root.wm_deiconify() #show window

def autoExecute(program):
    pyautogui.hotkey('win','r')
    pyperclip.copy(program)
    pyautogui.hotkey('ctrl','v')
    pyautogui.press('enter')
    
def work(question):
    global AIclient,AI_MODEL,img_offset,isRec
    if img_offset==4:
        if "自律" in question and "學生" in question: img_offset=0
        return
    if "你好" in question and "hi" in question:
        textReply('你好，有什麼需要我幫忙\n\n');return
    ii=question.find("播放")
    if ii>=0 and ii<len(question)-4:
        soundname=question[ii+2:]
        print("OK"+soundname)
        textReply('好的…馬上為您播放'+soundname)
        img_offset=6
        isRec = False
        play_youtube(soundname)
        time.sleep(1)
        return
    elif "開啟" in question and "小畫家" in question:
        autoExecute("mspaint")
    elif "開啟" in question and "記事本" in question:
        autoExecute("notepad")
    else:
        if len(question)<5:textReply('不清楚您的問題');return
        try:
            reply = GoogleAI產生文字(question)
        except Exception as e:
            print(f"Google AI 呼叫失敗：{e}")
            textReply('Google AI 呼叫失敗')
            return
        print(reply)
        textReplyLong(reply)


        
def  recJob():
  global isRec
  r = sr.Recognizer()
  r.pause_threshold = 0.5
  r.dynamic_energy_threshold = True
  while True:#錄音/辨識迴圈
      if not isRec:
          time.sleep(0.1)
          continue
      try:
          with sr.Microphone() as source:
              print("正在調整環境噪音...")
              r.adjust_for_ambient_noise(source, duration=0.5)
              print("請開始說話...")
              audio = r.listen(source, timeout=5, phrase_time_limit=10)

          result = r.recognize_google(audio, language='zh-TW')
          print(result)
          work(result)

      except sr.WaitTimeoutError:
          pass
      except sr.UnknownValueError:
          pass
      except sr.RequestError as e:
          print(f"辨識服務錯誤：{e}")
      except Exception as e:
          print(e)
      
def detectUserAction():
    global img_offset
    while True:
        if get_window(title='Roblox'):
            img_offset=4
            time.sleep(3)
            move(dx=-400,dy=0)
            T="快分科測驗了!不可開遊戲視窗!請對麥克風說：\n「我是自律的好學生」\n===========解鎖滑鼠============"
            textOn(T)
            engine.say(T);engine.runAndWait();engine.stop()
            while True:
                pyautogui.moveTo(500,500)
                if keyboard.is_pressed('esc'):break
                if img_offset==0:break
            img_offset=0
            time.sleep(3)
            textOn("")
            move(dx=400,dy=0)
            time.sleep(6)
            
        time.sleep(3)
        
#新增一執行緒 recJob 
recThread= threading.Thread( target=recJob)
recThread.start()
#新增一執行緒 detectUserAction
detectThread= threading.Thread( target=detectUserAction)
detectThread.start()
root.mainloop()
