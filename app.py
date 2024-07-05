
import os
import time
import uuid  
import wave


import azure.cognitiveservices.speech as speechsdk
import openai
import streamlit as st
from audio_recorder_streamlit import audio_recorder


openai.api_type = "azure"
openai.api_base = "https://wilmar-openai-api.openai.azure.com/"
openai.api_version = "2023-07-01-preview"
openai.api_key = os.environ.get('OPENAI_API_KEY')

# This example requires environment variables named "SPEECH_KEY" and "SPEECH_REGION"
speech_config = speechsdk.SpeechConfig(subscription=os.environ.get('SPEECH_KEY'), region="eastus")

# stream = speechsdk.audio.PushAudioInputStream()
# audio_config = speechsdk.audio.AudioConfig(stream=stream)

# Should be the locale for the speaker's language.
speech_config.speech_recognition_language="zh-CN"
# speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

# The language of the voice that responds on behalf of Azure OpenAI.
speech_config.speech_synthesis_voice_name='en-US-JennyMultilingualNeural'

pull_stream = speechsdk.audio.PullAudioOutputStream()
stream_config = speechsdk.audio.AudioOutputConfig(stream=pull_stream)
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=stream_config)

# tts sentence end mark
tts_sentence_end = [ ".", "!", "?", ";", "。", "！", "？", "；",]

def ask_and_reply(prompt, message_box):
    message_text = [
        {"role":"system","content":"你是个语音助理，我通过 . ! ? ; 。 ！ ？ ； \n 断句，请保证每次断句有10-20秒"},
        {"role":"user","content":prompt},
    ]

    completion = openai.ChatCompletion.create(
        engine="gpt-4o",
        messages = message_text,
        temperature=0.7,
        max_tokens=4096,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stream=True
    )

    print("OpenAI Request sent. Now waiting for response...")


    collected_messages = []
    for chunk in completion:
        # print(chunk)
        if len(chunk.choices) > 0:
            if "content" in chunk.choices[0].delta:
                print("Chunk:", chunk.choices[0].delta["content"])
                chunk_message = chunk.choices[0].delta.content  # extract the chunk message from openai output
                collected_messages.append(chunk_message)  # aggregate the message

                if chunk_message[0] in tts_sentence_end: # sentence end found
                    text = ''.join(collected_messages).strip() # join the recieved message together to build a sentence
                    if text != '': # if sentence only have \n or space, we could skip
                        #streaming audio output
                        print("Now playing: {}".format(text))
                        message_box.write(f'AI助理: {text}')
                        result = speech_synthesizer.speak_text(text)
                        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                            audio_data_stream = speechsdk.AudioDataStream(result)

                            unique_file_name = f"tempwav/{str(uuid.uuid4())}.wav"  # 生成唯一文件名  
                            audio_data_stream.save_to_wav_file(unique_file_name)  
                            audio = st.audio(unique_file_name, autoplay=True) 
                            
                            time.sleep(result.audio_duration.seconds+result.audio_duration.microseconds/1000000+1)
                            audio.empty() 
                            collected_messages.clear()
                            os.remove(unique_file_name)
                            # message_box.empty()


def push_stream_writer(stream,file_name):
    # The number of bytes to push per buffer
    n_bytes = 3200

    wav_fh = wave.open(file_name)
    # Start pushing data until all data has been read from the file
    try:
        while True:
            frames = wav_fh.readframes(n_bytes // 2)
            print('read {} bytes'.format(len(frames)))
            if not frames:
                break
            stream.write(frames)
            time.sleep(.1)
    finally:
        wav_fh.close()
        stream.close()  # must be done to signal the end of stream
    # os.remove(file_name)

def record_voice(file_name):
    # stream.write(wav_fh)
    # stream.close()  # must be done to signal the end of stream
    # push_stream_writer(stream,file_name)

    audio_config = speechsdk.AudioConfig(filename=file_name)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    # Get audio from the microphone and then send it to the TTS service.
    speech_recognition_result = speech_recognizer.recognize_once_async().get()

    if speech_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print("Recognized speech: {}".format(speech_recognition_result.text))
        st.session_state.prompt_text = speech_recognition_result.text
        st.session_state.voice_recognized = True

    elif speech_recognition_result.reason == speechsdk.ResultReason.NoMatch:
        print("No speech could be recognized: {}".format(speech_recognition_result.no_match_details))

    elif speech_recognition_result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = speech_recognition_result.cancellation_details
        print("Speech Recognition canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print("Error details: {}".format(cancellation_details.error_details))


# Initialize session state
if "prompt_text" not in st.session_state:
    st.session_state.prompt_text = None
if "voice_recognized" not in st.session_state:
    st.session_state.voice_recognized = False

# lottie_anim = load_json_from_file('./lottie.json')
gif_file_path = "./static/yihai.jpg"

st.set_page_config(page_title="AI 语音", page_icon='', layout='centered')

with st.container():
    left, right = st.columns([2, 3])
    with left:
        # st_lottie(lottie_anim, speed=0.5, height=300, key="coding")
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
                energy_threshold=(-1.0, 1.0),
                pause_threshold=3.0,
                sample_rate=32000
        )

        if wav_audio_data is not None:
            file_name = f"input/{str(uuid.uuid4())}.wav"
            # save audio file to mp3
            with open(file_name, "wb") as f:
                f.write(wav_audio_data)
            record_voice(file_name)
        # rec_button = st.button(
        #     label="说话", type='primary',
        #     on_click=record_voice)

        message_box = st.empty()
        if st.session_state.voice_recognized:
            message_box.write(f'你: {st.session_state.prompt_text}')

            # Send the prompt to OpenAI
            ask_and_reply(st.session_state.prompt_text, message_box)
            st.session_state.prompt_text = None
            st.session_state.voice_recognized = False