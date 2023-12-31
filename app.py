import tkinter as tk
from PIL import Image, ImageTk
import requests, time, math, os
from threading import Thread
from scipy.io.wavfile import write
import sounddevice as sd
from util.map_color import map_color
from model.apl.infer import ModelInference
from util.util import generate_mdd_for_app, get_phoneme_ipa_form

url = "http://127.0.0.1:8085"
# url = 'https://f85a-35-196-52-119.ngrok-free.app'
current_folder = os.path.dirname(os.path.realpath(__file__))
img_folder = os.path.join(current_folder, 'img')
audio_folder = os.path.join(current_folder, 'audio')
if not os.path.exists(audio_folder):
    os.mkdir(audio_folder)

class FirstFrame:
    def __init__(self, app):
        self.app = app
        self.width_element = 450
        self.pos_x = (self.app.window_width - self.width_element) // 2
        self.frame = tk.Frame(self.app.root, background='#0d1b2a')
        self.frame.pack(fill='both', side='top', expand=True)
        self.entry = tk.Entry(self.frame, font=("Helvetica", 14, "normal"))
        self.frame.img = self.load_image('search.png', self.width_element, 40)
        self.entry.place(x=self.pos_x, y=50, height=50, width=self.width_element)
        self.button = tk.Button(self.frame, image=self.frame.img, command=self.search, relief='flat', borderwidth=0 , highlightthickness=0)
        self.button.place(x=self.pos_x, y=120, width=self.width_element)

    def load_image(self, path, width, height):
        img = Image.open(os.path.join(img_folder, path))
        img = img.resize((width,height))
        img = ImageTk.PhotoImage(img)
        return img
    
    def search(self):
        def run_thread():
            try:
                print("Searching")
                text = self.entry.get()
                self.button.config(state=tk.DISABLED)
                if self.app.is_online():
                    result = requests.post(url=f'{url}/phonemes', data={'text':text}).text
                    result = eval(result)
                else:
                    result = get_phoneme_ipa_form(text)
                frame = SecondFrame(self.app, text, result['phonetics'])
                self.app.set_frame(frame)
            except Exception as e:
                print(f"Error in search function: {e}")
        t = Thread(target=run_thread, daemon=True)
        t.start()

    def destroy(self):
        self.frame.destroy()
        

class SecondFrame:
    def __init__(self, app, text_talk, text_phoneme):
        self.app = app
        self.background_color = 'white'
        self.is_playing_record = False
        self.save_file_temp = os.path.join(audio_folder, 'test_app.wav')
        self.result_frame = None
        self.time_count = 0
        self.sample_rate = 16000
        self.max_length = 1000
        self.create_menu_bar()
        self.is_recording = False
        self.text_talk = text_talk
        self.text_phoneme = text_phoneme
        self.frame = tk.Frame(self.app.root, background=self.background_color)
        self.frame.pack(fill='both', side='top', expand=True)
        self.create_record_button()
        self.create_text()

    def create_menu_bar(self):
        self.menu_frame = tk.Frame(self.app.root, background=self.background_color, height=50)
        self.menu_frame.pack(fill='x', pady=(0, 10))
        self.menu_frame.img = self.load_image("exit.png", 20, 20)
        button = tk.Button(
            self.menu_frame, image=self.menu_frame.img, command=self.back, 
            background=self.background_color, relief='flat', borderwidth=0 , highlightthickness=0
        )
        button.pack(side='left', pady=10, padx=10)

    def back(self):
        if self.is_playing_record:
            return
        frame = FirstFrame(self.app)
        self.app.set_frame(frame)

    def create_text(self):
        # for text 
        self.text_talk_frame = tk.Text(self.frame, borderwidth=0, font=("Helvetica", 18, "normal"))
        self.text_talk_frame.insert(tk.INSERT, self.text_talk)
        num_lines = len(self.text_talk) // 30
        self.text_talk_frame.config(state=tk.DISABLED, height=num_lines)
        self.text_talk_frame.pack(side='top', anchor='nw', padx=30, pady=(40, 10))

        # for phoneme
        self.text_phoneme_frame = tk.Text(self.frame, borderwidth=0)
        self.show_text_phoneme([(self.text_phoneme, " ", 1, 'black')])
        self.text_phoneme_frame.pack(side='top', anchor='nw', padx=30)

    def show_text_phoneme(self, dict_phoneme_tag):
        try:
            self.text_phoneme_frame.config(state=tk.NORMAL)
            self.text_phoneme_frame.delete("1.0","end")
            tag_names = self.text_phoneme_frame.tag_names()
            [self.text_phoneme_frame.tag_delete(tn) for tn in tag_names]

            self.text_phoneme_frame.insert(tk.INSERT, '/')
            for i, data in enumerate(dict_phoneme_tag):
                right_phoneme, predict_phoneme, right_phoneme_score, color = data
                tag_name = f'tag_{i}|{right_phoneme}|{predict_phoneme}|{right_phoneme_score}'
                self.text_phoneme_frame.insert(tk.INSERT, right_phoneme, tag_name)
                self.text_phoneme_frame.tag_config(tag_name, foreground=color)
                if color != 'black':
                    self.text_phoneme_frame.tag_bind(tag_name, "<Button-1>", self.show_compare_window)
            self.text_phoneme_frame.insert(tk.INSERT, '/')
            self.text_phoneme_frame.config(state=tk.DISABLED)
        except Exception as e:
            print(f'show_text_phoneme: {e}')

    def create_record_button(self):
        self.record_btn_size = 100
        self.record_audio = None
        self.frame.img = img = self.load_image("normal.png", self.record_btn_size,self.record_btn_size)
        self.record_btn = tk.Button(self.frame, image=img, width=self.record_btn_size, height=self.record_btn_size, relief='flat', borderwidth=0 , highlightthickness=0, command=self.handle_record_button)
        self.record_btn.config(image=img)
        self.record_btn.pack(side='bottom', pady=20)

    def load_image(self, path, width, height):
        img = Image.open(os.path.join(img_folder, path))
        img = img.resize((width,height))
        img = ImageTk.PhotoImage(img)
        return img
    
    def handle_record_button(self):
        if self.is_recording:
            self.stop_record()
        else:
            self.start_record()

    def start_record(self):
        if self.result_frame is not None:
            self.result_frame.destroy()
        if self.is_playing_record:
            return
        self.time_count = time.time()
        self.record_audio = sd.rec(self.max_length * self.sample_rate ,samplerate=self.sample_rate, channels=1)
        self.is_recording = True
        self.frame.img = self.load_image("recording.png", self.record_btn_size,self.record_btn_size)
        self.record_btn.config(image=self.frame.img)
        self.show_text_phoneme([(self.text_phoneme, " ", 1, 'black')])

    def stop_record(self):
        self.is_recording = False
        sd.stop()
        self.record_audio = self.record_audio[:math.ceil(time.time()-self.time_count)*self.sample_rate]
        self.time_count = 0
        write(self.save_file_temp, self.sample_rate, self.record_audio)
        self.frame.img = self.load_image("normal.png", self.record_btn_size,self.record_btn_size)
        self.record_btn.config(image=self.frame.img)
        t = Thread(target=self.submit)
        t.start()

    def submit(self):
        try:
            print("Analysing")
            text = self.text_talk
            self.record_btn.config(state=tk.DISABLED)

            if self.app.is_online():
                with open(self.save_file_temp, 'rb') as f:
                    result = requests.post(url=f'{url}/predict', data={'text':text}, files={'audio': f}).text
                result = eval(result)
            else:
                self.app.wait_until_model_ready()
                log_proba, canonical, word_phoneme_in = self.app.offline_model.infer(text, self.save_file_temp)
                result = generate_mdd_for_app(log_proba, canonical, word_phoneme_in)

            self.map_phoneme_color = map_color(eval(result['phoneme_result']))
            self.show_text_phoneme(self.map_phoneme_color)
            
            self.record_btn.config(state=tk.NORMAL)
            self.create_show_result(float(result['correct_rate']))
        except Exception as e:
            print(f"Error in submit function: {e}")

    def play_recording(self):
        if self.is_playing_record:
            return
        print('start play recording')
        def run_thread():
            self.is_playing_record = True
            sd.playrec(self.record_audio,samplerate=self.sample_rate, channels=1)
            sd.wait()
            self.is_playing_record = False
        t = Thread(target=run_thread, daemon=True)
        t.start()

    def show_compare_window(self, event):
        try:
            tag_name = event.widget.tag_names(tk.CURRENT)[0]
            # print("Clicked on tags:", tag_name)
            _, right_phoneme, predict_phoneme, right_score = tag_name.split('|')
            # print(f"Right phoneme: {right_phoneme}, You said: {predict_phoneme}, Score: {right_score}")

            self.show_text_phoneme(self.map_phoneme_color)
            self.text_phoneme_frame.config(state=tk.NORMAL)
            self.text_phoneme_frame.insert(tk.INSERT, f"\n\nSound: {right_phoneme}")
            self.text_phoneme_frame.insert(tk.INSERT, f"\nYou said: {predict_phoneme}")
            self.text_phoneme_frame.insert(tk.INSERT, f"\nScore: {round(float(right_score)*100)}%")
            self.text_phoneme_frame.config(state=tk.DISABLED)
        except Exception as e:
            print(f"Show compare window: {e}")
        
    def create_show_result(self, correct_rate):
        correct_rate = round(correct_rate * 100)
        font_large = ("Helvetica", 20, "normal")
        if correct_rate < 40:
            color = '#d00000'
            temp = 'Try Again'
        elif correct_rate < 80:
            color = '#ff9f1c'
            temp = 'Almost Correct'
        else:
            temp = 'Excellent!'
            color = '#70AD47'

        self.result_frame = tk.Frame(self.app.root, background='#CDCDCD')
        self.result_frame.place(x=0, y=self.app.window_height - 300, width=self.app.window_width, height=300)
        frame1 = tk.Frame(self.result_frame, background=self.background_color, height=75)
        frame1.pack(fill='x', pady=1)
        label = tk.Label(frame1, text=temp, foreground=color, background=self.background_color, font=font_large)
        label.pack(side='left', padx=20, pady=10)
        frame1.img = self.load_image('ear.png', width=30, height=30)
        btn = tk.Button(frame1, width=30, height=30, image=frame1.img, relief='flat', borderwidth=0 , highlightthickness=0, command=self.play_recording)
        btn.pack(side='right', padx=20)

        frame2 = tk.Frame(self.result_frame, background=self.background_color, height=225)
        frame2.pack(fill='x')
        label = tk.Label(frame2, background=self.background_color)
        label.pack(side='top', pady=10)
        label = tk.Label(frame2, text=f'You sound {correct_rate}% like a native speaker!', background=self.background_color, font=("Helvetica", 12, "normal"))
        label.place(x=20, y=10)
        frame2.img1 = self.load_image(f'try_again_btn{color}.png', 400, 75)
        btn = tk.Button(frame2, image=frame2.img1, width=400, height=75, relief='flat', borderwidth=0 , highlightthickness=0, command=self.start_record)
        btn.pack(side='top', pady=10)
        frame2.img2 = self.load_image('try_new_word_btn.png', 400, 75)
        btn = tk.Button(frame2, image=frame2.img2, width=400, height=75, relief='flat', borderwidth=0 , highlightthickness=0, command=self.back)
        btn.pack(side='top', pady=(10, 0))
        label = tk.Label(frame2)
        label.pack(pady=20)


    def destroy(self):
        self.frame.destroy()
        self.menu_frame.destroy()
        if self.result_frame is not None:
            self.result_frame.destroy()


class Application:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("English App Using AI")
        self.online = True
        self.model_ready = False
        t = Thread(target=self.init_model, daemon=True)
        t.start()
        self.window_width = 500
        self.window_height = 650
        self.root.geometry(f'{self.window_width}x{self.window_height}')
        self.root.resizable(False, False)
        self.frame = FirstFrame(self)

    def init_model(self):
        self.offline_model = ModelInference()
        self.model_ready = True

    def wait_until_model_ready(self):
        while True:
            if self.model_ready:
                return
            time.sleep(1)

    def set_frame(self, frame):
        self.frame.destroy()
        self.frame = frame

    def run(self):
        self.root.mainloop()

    def is_online(self):
        return self.online


if __name__ == '__main__':
    app = Application()
    app.run()