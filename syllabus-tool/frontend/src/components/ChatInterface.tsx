import { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
import { DiffViewer } from './DiffViewer';

interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  suggested_changes?: any;
}

export interface ChatInterfaceRef {
  setInput: (text: string) => void;
  sendMessage: (text: string) => void;
}

interface ChatInterfaceProps {
  context?: string;
  onApplyChanges?: (changes: any) => void;
}

export const ChatInterface = forwardRef<ChatInterfaceRef, ChatInterfaceProps>(({ context, onApplyChanges }, ref) => {
  const [messages, setMessages] = useState<Message[]>([
    { id: 1, role: 'assistant', content: 'Hello! I can help you refine your syllabus. Try asking me to "Rewrite the learning goals" or "Add a policy about AI usage".' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const adjustHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  };

  useEffect(() => {
    adjustHeight();
  }, [input]);

  useImperativeHandle(ref, () => ({
    setInput: (text: string) => setInput(text),
    sendMessage: (text: string) => handleSend(text)
  }));

  const handleSend = async (messageOverride?: string) => {
    const messageToSend = messageOverride || input;
    if (!messageToSend.trim() || isLoading) return;

    const userMsg: Message = { id: Date.now(), role: 'user', content: messageToSend };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setIsLoading(true);

    // Create a placeholder message for AI response
    const aiMsgId = Date.now() + 1;
    setMessages(prev => [...prev, { id: aiMsgId, role: 'assistant', content: '' }]);

    try {
      // apiUrl is expected to include the version prefix (e.g., /api/v1)
      const response = await fetch(`${apiUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          message: userMsg.content,
          context: context 
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : JSON.stringify(errorData.detail) || 'Failed to get response from AI';
        throw new Error(errorMessage);
      }

      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        accumulatedContent += chunk;
        
        setMessages(prev => prev.map(msg => 
          msg.id === aiMsgId 
            ? { ...msg, content: accumulatedContent } 
            : msg
        ));
      }

      // Final processing to extract JSON
      let suggestedChanges = undefined;
      
      // Try to find JSON block at the end
      const jsonBlockRegex = /```json\s*([\s\S]*?)\s*```/;
      const match = accumulatedContent.match(jsonBlockRegex);
      
      if (match) {
        try {
            suggestedChanges = JSON.parse(match[1]);
        } catch (e) {
            console.error("Failed to parse JSON from stream", e);
        }
      }

      setMessages(prev => prev.map(msg => 
        msg.id === aiMsgId 
          ? { ...msg, content: accumulatedContent, suggested_changes: suggestedChanges } 
          : msg
      ));

    } catch (error) {
      console.error('Error calling AI:', error);
      setMessages(prev => prev.map(msg => 
        msg.id === aiMsgId 
          ? { ...msg, content: error instanceof Error ? error.message : 'Sorry, I encountered an error while processing your request.' } 
          : msg
      ));
    } finally {
      setIsLoading(false);
    }
  };

  // Helper to extract old text from context for diffing
  const getOldTextForDiff = (changes: any): string => {
    if (!context) return '';
    try {
      // Parse the context string to find the relevant section
      // Context format: "Raw Text Context:\n...\n\nCurrent Structured Data:\n{...}"
      const jsonStart = context.indexOf('Current Structured Data:\n') + 'Current Structured Data:\n'.length;
      const currentData = JSON.parse(context.substring(jsonStart));
      
      // Simple heuristic: if changing learning goals, show diff of learning goals text
      if (changes.learning_goals) {
        return currentData.learning_goals.map((g: any) => g.text).join('\n');
      }
      if (changes.policies) {
        return Object.values(currentData.policies).join('\n\n');
      }
      // Fallback
      return '';
    } catch (e) {
      return '';
    }
  };

  const getNewTextForDiff = (changes: any): string => {
    if (changes.learning_goals) {
      return changes.learning_goals.map((g: any) => g.text).join('\n');
    }
    if (changes.policies) {
      return Object.values(changes.policies).join('\n\n');
    }
    return '';
  };

  return (
    <div className="bg-white shadow rounded-lg flex flex-col h-full">
      <div className="p-2 sm:p-4 border-b bg-gray-50 rounded-t-lg">
        <h3 className="font-medium text-gray-700 text-xs sm:text-base">AI Assistant</h3>
      </div>
      
      <div className="flex-1 overflow-y-auto p-2 sm:p-4 space-y-2 sm:space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
          >
            <div
              className={`max-w-[95%] sm:max-w-[90%] rounded-lg px-2 sm:px-4 py-1 sm:py-2 text-[10px] sm:text-sm ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-800'
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>
              {msg.suggested_changes && onApplyChanges && (
                <div className="mt-1 sm:mt-2 pt-1 sm:pt-2 border-t border-gray-200">
                  <p className="text-[8px] sm:text-xs text-gray-500 mb-1 sm:mb-2 font-semibold">Suggested Changes:</p>
                  
                  {/* Diff View for specific sections */}
                  {(msg.suggested_changes.learning_goals || msg.suggested_changes.policies) && (
                    <div className="mb-2 sm:mb-3 max-h-40 overflow-y-auto border rounded bg-white">
                       <DiffViewer 
                          oldText={getOldTextForDiff(msg.suggested_changes)} 
                          newText={getNewTextForDiff(msg.suggested_changes)} 
                       />
                    </div>
                  )}

                  <button
                    onClick={() => onApplyChanges(msg.suggested_changes)}
                    className="bg-green-600 text-white px-2 sm:px-3 py-0.5 sm:py-1 rounded text-[8px] sm:text-xs hover:bg-green-700 transition-colors w-full sm:w-auto"
                  >
                    Apply Changes
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 text-gray-800 rounded-lg px-2 sm:px-4 py-1 sm:py-2 text-[10px] sm:text-sm">
              Thinking...
            </div>
          </div>
        )}
      </div>

      <div className="p-2 sm:p-4 border-t">
        <div className="flex gap-1 sm:gap-2 items-end">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask AI..."
            disabled={isLoading}
            rows={1}
            className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-[10px] sm:text-sm border p-1 sm:p-2 disabled:bg-gray-100 resize-y min-h-[30px] sm:min-h-[38px] max-h-[150px] sm:max-h-[200px] overflow-y-auto"
          />
          <button
            onClick={() => handleSend()}
            disabled={isLoading}
            className="bg-blue-600 text-white px-2 sm:px-4 py-1 sm:py-2 rounded-md hover:bg-blue-700 text-[10px] sm:text-sm font-medium disabled:bg-blue-400 h-[30px] sm:h-[38px]"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
});

