import { diffWords } from 'diff';
import clsx from 'clsx';

interface DiffViewerProps {
  oldText: string;
  newText: string;
}

export function DiffViewer({ oldText, newText }: DiffViewerProps) {
  const diff = diffWords(oldText, newText);

  return (
    <div className="text-sm font-mono bg-gray-50 p-2 rounded border">
      {diff.map((part, index) => (
        <span
          key={index}
          className={clsx(
            part.added && 'bg-green-200 text-green-800',
            part.removed && 'bg-red-200 text-red-800 line-through',
            !part.added && !part.removed && 'text-gray-600'
          )}
        >
          {part.value}
        </span>
      ))}
    </div>
  );
}
