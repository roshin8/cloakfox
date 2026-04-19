import React from 'react';
import type { ContainerIdentity } from '@/types';
import { CONTAINER_COLORS } from '@/lib/constants';

interface Props {
  containers: ContainerIdentity[];
  selectedContainer: string | null;
  currentContainer?: string;
  onSelect: (containerId: string) => void;
}

export default function ContainerSelector({
  containers,
  selectedContainer,
  currentContainer,
  onSelect,
}: Props) {
  const getContainerColor = (color: string): string => {
    return (
      CONTAINER_COLORS[color as keyof typeof CONTAINER_COLORS] || '#7c7c7d'
    );
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-400">
        Configure Container
      </label>
      <div className="flex flex-wrap gap-2">
        {containers.map((container) => {
          const isSelected = container.cookieStoreId === selectedContainer;
          const isCurrent = container.cookieStoreId === currentContainer;
          const color = getContainerColor(container.color);

          return (
            <button
              key={container.cookieStoreId}
              onClick={() => onSelect(container.cookieStoreId)}
              className={`
                px-3 py-1.5 rounded-full text-sm font-medium
                transition-all duration-200
                ${
                  isSelected
                    ? 'ring-2 ring-offset-2 ring-offset-gray-800'
                    : 'hover:opacity-80'
                }
              `}
              style={{
                backgroundColor: isSelected ? color : `${color}33`,
                color: isSelected ? '#fff' : color,
                borderColor: color,
                ['--tw-ring-color' as any]: color,
              }}
            >
              {container.name}
              {isCurrent && (
                <span className="ml-1 text-xs opacity-70">(current)</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
