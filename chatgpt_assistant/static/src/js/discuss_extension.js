odoo.define('chatgpt_assistant.discuss_extension', [], function (Discuss, utils) {
    "use strict";

    const { patch } = utils;

    patch(Discuss.prototype, 'chatgpt_assistant.discuss_extension', {
        async _onChatGPTSendMessage(event) {
            const message = this.inputValue || '';
            if (!message.trim()) {
                return;
            }

            try {
                const result = await this.env.services.rpc({
                    route: '/discuss/chatgpt',
                    params: { message },
                });

                if (result.response) {
                    this._insertMessage(result.response);
                }
            } catch (error) {
                console.error('Erreur lors de l\'appel à ChatGPT:', error);
                this._insertMessage('Erreur : Impossible de contacter ChatGPT.');
            }
        },
    });
});