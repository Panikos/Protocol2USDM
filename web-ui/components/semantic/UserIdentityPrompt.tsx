'use client';

import { useState } from 'react';
import { User, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useUserIdentity } from '@/hooks/useUserIdentity';

/**
 * Inline prompt for setting user identity.
 * Shows when username is 'anonymous'. Can be dismissed after entry.
 */
export function UserIdentityBanner() {
  const { username, setUsername, needsIdentity, isAnonymous } = useUserIdentity();
  const [inputValue, setInputValue] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  if (dismissed && !isEditing) return null;
  if (!needsIdentity && !isEditing) return null;

  const handleSubmit = () => {
    if (inputValue.trim()) {
      setUsername(inputValue.trim());
      setIsEditing(false);
      setDismissed(true);
    }
  };

  return (
    <div className="flex items-center gap-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded-md text-sm">
      <User className="h-4 w-4 text-amber-600 shrink-0" />
      <span className="text-amber-800">
        {isAnonymous ? 'Set your identity for audit trail:' : `Editing as: ${username}`}
      </span>
      <input
        type="text"
        className="border border-amber-300 rounded px-2 py-1 text-sm bg-white w-48"
        placeholder="Your name"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit(); }}
        autoFocus
      />
      <Button size="sm" variant="outline" onClick={handleSubmit} disabled={!inputValue.trim()}>
        <Check className="h-3 w-3 mr-1" />
        Set
      </Button>
      {!isAnonymous && (
        <Button size="sm" variant="ghost" onClick={() => { setIsEditing(false); setDismissed(true); }}>
          Cancel
        </Button>
      )}
    </div>
  );
}

/**
 * Small badge showing current user identity. Click to edit.
 */
export function UserIdentityBadge() {
  const { username, isAnonymous } = useUserIdentity();
  const [isEditing, setIsEditing] = useState(false);

  if (isEditing) {
    return <UserIdentityBanner />;
  }

  return (
    <button
      onClick={() => setIsEditing(true)}
      className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-colors ${
        isAnonymous
          ? 'bg-amber-100 text-amber-700 hover:bg-amber-200'
          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
      }`}
      title="Click to change identity"
    >
      <User className="h-3 w-3" />
      {username}
    </button>
  );
}
