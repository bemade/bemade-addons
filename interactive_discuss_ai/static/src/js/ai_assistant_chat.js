/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { attr } from '@mail/model/model_field';
import { clear } from '@mail/model/model_field_command';

registerPatch({
    name: 'mail.composer',
    fields: {
        isVoiceRecording: attr({
            default: false,
        }),
    },
    recordMethods: {
        async onClickVoiceRecord() {
            if (!this.isVoiceRecording) {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    this.mediaRecorder = new MediaRecorder(stream);
                    const audioChunks = [];

                    this.mediaRecorder.addEventListener('dataavailable', (event) => {
                        audioChunks.push(event.data);
                    });

                    this.mediaRecorder.addEventListener('stop', async () => {
                        const audioBlob = new Blob(audioChunks);
                        // Convert to base64 and send to backend
                        const reader = new FileReader();
                        reader.readAsDataURL(audioBlob);
                        reader.onloadend = async () => {
                            const base64data = reader.result;
                            await this.env.services.rpc({
                                model: 'ai.assistant.channel',
                                method: 'process_voice_message',
                                args: [this.thread.id, base64data],
                            });
                        };
                    });

                    this.mediaRecorder.start();
                    this.update({ isVoiceRecording: true });
                } catch (err) {
                    console.error('Error accessing microphone:', err);
                }
            } else {
                this.mediaRecorder.stop();
                this.update({ isVoiceRecording: false });
            }
        },
    },
});
