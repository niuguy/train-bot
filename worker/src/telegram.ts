export interface TelegramMessageEntity {
  type: string;
  offset: number;
  length: number;
}

export interface TelegramChat {
  id: number | string;
  type: string;
}

export interface TelegramMessage {
  message_id: number;
  date: number;
  chat: TelegramChat;
  text?: string;
  entities?: TelegramMessageEntity[];
}

export interface TelegramUpdate {
  update_id: number;
  message?: TelegramMessage;
}

export class TelegramBot {
  private readonly apiUrl: string;

  constructor(private readonly token: string) {
    this.apiUrl = `https://api.telegram.org/bot${token}`;
  }

  async sendMessage(chatId: number | string, text: string): Promise<void> {
    const response = await fetch(`${this.apiUrl}/sendMessage`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        chat_id: chatId,
        text,
        disable_web_page_preview: true
      })
    });

    if (!response.ok) {
      const snippet = await response.text();
      console.error("Telegram sendMessage failed", response.status, snippet);
      throw new Error(`Telegram API error ${response.status}`);
    }
  }
}
