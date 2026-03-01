import React, { useEffect, useState, useRef } from 'react';
import { createPortal } from 'react-dom';

interface FloatingMenuProps {
  onAction: (prompt: string) => void;
  containerRef: React.RefObject<HTMLElement>;
}

export const FloatingMenu: React.FC<FloatingMenuProps> = ({ onAction, containerRef }) => {
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const [selectedText, setSelectedText] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleSelectionChange = () => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed || !selection.toString().trim()) {
        setVisible(false);
        return;
      }

      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      
      // Check if selection is within container
      if (containerRef.current && !containerRef.current.contains(range.commonAncestorContainer)) {
        setVisible(false);
        return;
      }

      setSelectedText(selection.toString());
      setPosition({
        top: rect.top - 40 + window.scrollY, // Position above selection
        left: rect.left + rect.width / 2 + window.scrollX,
      });
      setVisible(true);
    };

    document.addEventListener('selectionchange', handleSelectionChange);
    return () => document.removeEventListener('selectionchange', handleSelectionChange);
  }, [containerRef]);

  if (!visible) return null;

  const handleClick = (action: string) => {
    const prompt = `${action}: "${selectedText}"`;
    onAction(prompt);
    setVisible(false);
    window.getSelection()?.removeAllRanges();
  };

  return createPortal(
    <div
      ref={menuRef}
      style={{ top: position.top, left: position.left, transform: 'translateX(-50%)' }}
      className="fixed z-50 bg-gray-800 text-white rounded shadow-lg flex overflow-hidden text-[10px] sm:text-xs"
      onMouseDown={(e) => e.preventDefault()} // Prevent losing selection
    >
      <button onClick={() => handleClick('Refine')} className="px-2 sm:px-3 py-1 sm:py-2 hover:bg-gray-700 border-r border-gray-700">Refine</button>
      <button onClick={() => handleClick('Shorten')} className="px-2 sm:px-3 py-1 sm:py-2 hover:bg-gray-700 border-r border-gray-700">Shorten</button>
      <button onClick={() => handleClick('Fix Grammar')} className="px-2 sm:px-3 py-1 sm:py-2 hover:bg-gray-700">Fix Grammar</button>
    </div>,
    document.body
  );
};
