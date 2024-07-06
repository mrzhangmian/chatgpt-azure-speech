import os  
import time  
import uuid  
import wave  
import azure.cognitiveservices.speech as speechsdk  
import openai  
import streamlit as st  
from audio_recorder_streamlit import audio_recorder  
  
# 配置 OpenAI 和 Azure API  
openai.api_type = "azure"  
openai.api_base = "https://wilmar-openai-api.openai.azure.com/"  
openai.api_version = "2023-07-01-preview"  
openai.api_key = os.environ.get('OPENAI_API_KEY')  
  
speech_config = speechsdk.SpeechConfig(subscription=os.environ.get('SPEECH_KEY'), region="eastus")  
speech_config.speech_recognition_language = "zh-CN"  
speech_config.speech_synthesis_voice_name = 'zh-CN-YunxiNeural'  
pull_stream = speechsdk.audio.PullAudioOutputStream()  
stream_config = speechsdk.audio.AudioOutputConfig(stream=pull_stream)  
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=stream_config)  
  
tts_sentence_end = ["!", "?", ";", "。", "！", "？", "；"]  
  
# 系统提示词，作为对话的上下文  
system_message = [{  
    "role": "system",  
    "content": "你是一个语音助理。APi返回模式设置stream，请确保每次chunk结尾是以下标点 . ! ? ; 。 ！ ？ ；"  
} ] 
  
def ask_and_reply(prompt, message_box):  
    # 将历史对话记录与当前输入合并  
    history = st.session_state.get("chat_history", [])  
    history.append({"role": "user", "content": prompt})  
      
    # 确保历史记录最多包含20条（包含系统提示词）  
    if len(history) > 21:  
        history = history[-21:]  
    message = system_message + history
    completion = openai.ChatCompletion.create(  
        engine="gpt-4o",  
        messages=message,  
        temperature=0.7,  
        max_tokens=4096,  
        top_p=0.95,  
        frequency_penalty=0,  
        presence_penalty=0,  
        stream=True  
    )  
    # print(message)
    # print("OpenAI Request sent. Now waiting for response...")  
    collected_messages = []  
    assistant_messages = []  
    for chunk in completion:  
        if len(chunk.choices) > 0:  
            if "content" in chunk.choices[0].delta:  
                chunk_message = chunk.choices[0].delta.content  
                collected_messages.append(chunk_message)  
                if chunk_message and chunk_message[-1] in tts_sentence_end:  
                    text = ''.join(collected_messages).strip()  
                    if text:  
                        # print("Now playing: {}".format(text))  
                        message_box.write(f'AI助理: {text}')  
                        result = speech_synthesizer.speak_text(text)  
                        assistant_messages.append(text)
                        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:  
                            audio_data_stream = speechsdk.AudioDataStream(result)  
                            unique_file_name = f"tempwav/{str(uuid.uuid4())}.wav"  
                            audio_data_stream.save_to_wav_file(unique_file_name)  
                            audio = st.audio(unique_file_name, autoplay=True)  
                            time.sleep(result.audio_duration.seconds + result.audio_duration.microseconds / 1000000 + 1)  
                            audio.empty()  
                            os.remove(unique_file_name)  
                            collected_messages.clear()
      
    # 将 AI 的回复添加到历史记录中  
    history.append({"role": "assistant", "content": ''.join(assistant_messages).strip()})  
    assistant_messages.clear()
    st.session_state.chat_history = history  
  
def record_voice(wav_audio_data):  

    file_name = f"input/{str(uuid.uuid4())}.wav"  
    with open(file_name, "wb") as f:  
        f.write(wav_audio_data)  

    audio_config = speechsdk.AudioConfig(filename=file_name)  
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)  
    speech_recognition_result = speech_recognizer.recognize_once_async().get()  
    if speech_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:  
        # print("Recognized speech: {}".format(speech_recognition_result.text))  
        st.session_state.prompt_text = speech_recognition_result.text  
        st.session_state.voice_recognized = True  
    elif speech_recognition_result.reason == speechsdk.ResultReason.NoMatch:  
        print("No speech could be recognized: {}".format(speech_recognition_result.no_match_details))  
    elif speech_recognition_result.reason == speechsdk.ResultReason.Canceled:  
        cancellation_details = speech_recognition_result.cancellation_details  
        print("Speech Recognition canceled: {}".format(cancellation_details.reason))  
        if cancellation_details.reason == speechsdk.CancellationReason.Error:  
            print("Error details: {}".format(cancellation_details.error_details)) 
  
if "prompt_text" not in st.session_state:  
    st.session_state.prompt_text = None  
if "voice_recognized" not in st.session_state:  
    st.session_state.voice_recognized = False  
if "chat_history" not in st.session_state:  
    st.session_state.chat_history = []  
  
gif_file_path = "./static/yihai.jpg"  
st.set_page_config(page_title="AI 语音", page_icon='', layout='centered')  
  
with st.container():  
    left, right = st.columns([2, 3])  
    with left:  
        st.image(gif_file_path)  
    with right:  
        st.subheader('益海嘉里 语音助理')  
        st.write('点击 麦克风 问我问题.')  
        wav_audio_data = audio_recorder(  
            text="",  
            recording_color="#e8b62c",  
            neutral_color="#6aa36f",  
            icon_name="microphone",  
            icon_size="2x",  
            energy_threshold=(-10.0, 0.1),  
            pause_threshold=3.0,  
            sample_rate=32000,
        )  
        if wav_audio_data is not None:  
            record_voice(wav_audio_data)  
  
        message_box = st.empty()  
        if st.session_state.voice_recognized:  
            message_box.write(f'你: {st.session_state.prompt_text}')  
            ask_and_reply(st.session_state.prompt_text, message_box)  
            st.session_state.prompt_text = None  
            st.session_state.voice_recognized = False  
