import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core';
import { useState } from 'react';
import type { Card, ViewGroup } from '../types';
import { UNSORTED_ID } from '../types';
import { categoryHue, countCards } from '../util';
import { CardRow } from './CardRow';
import { usePreview } from './HoverPreview';

export interface BoardEditHandlers {
  onMove: (cardKey: string, toGroupId: string) => void;
  onRename: (groupId: string, name: string) => void;
  onDelete: (groupId: string) => void;
  onShift: (groupId: string, delta: -1 | 1) => void;
  onAdd: (name: string) => void;
}

interface Props {
  groups: ViewGroup[];
  selectedKey: string | null;
  onSelect: (card: Card) => void;
  /** Present only for custom groupings: enables drag-and-drop and group editing. */
  edit?: BoardEditHandlers;
  colorize: boolean;
}

export function BoardView({ groups, selectedKey, onSelect, edit, colorize }: Props) {
  const sensors = useSensors(
    // Small distance so a plain click still opens card details.
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );
  const [active, setActive] = useState<Card | null>(null);
  const preview = usePreview();

  const onDragStart = (e: DragStartEvent) => {
    preview.suppress(true);
    setActive((e.active.data.current?.card as Card) ?? null);
  };
  const onDragEnd = (e: DragEndEvent) => {
    preview.suppress(false);
    setActive(null);
    const card = e.active.data.current?.card as Card | undefined;
    const from = e.active.data.current?.groupId as string | undefined;
    if (edit && card && e.over && e.over.id !== from) edit.onMove(card.key, String(e.over.id));
  };

  return (
    <DndContext
      sensors={sensors}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragCancel={() => {
        preview.suppress(false);
        setActive(null);
      }}
    >
      <div className="board">
        {groups.map((g, i) => (
          <Column
            key={g.id}
            group={g}
            selectedKey={selectedKey}
            onSelect={onSelect}
            edit={edit}
            colorize={colorize}
            isFirst={i === 0 || groups[i - 1].id === UNSORTED_ID}
            isLast={i === groups.length - 1}
          />
        ))}
        {edit && <AddColumn onAdd={edit.onAdd} />}
      </div>
      <DragOverlay dropAnimation={null}>{active && <CardRow card={active} overlay />}</DragOverlay>
    </DndContext>
  );
}

function Column({
  group,
  selectedKey,
  onSelect,
  edit,
  colorize,
  isFirst,
  isLast,
}: {
  group: ViewGroup;
  selectedKey: string | null;
  onSelect: (card: Card) => void;
  edit?: BoardEditHandlers;
  colorize: boolean;
  isFirst: boolean;
  isLast: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: group.id, disabled: !edit });
  const [renaming, setRenaming] = useState(false);
  const isUnsorted = group.id === UNSORTED_ID;
  const accent = colorize ? `hsl(${categoryHue(group.name)} 55% 50%)` : undefined;

  return (
    <section
      ref={setNodeRef}
      className={`column${isOver ? ' drop-over' : ''}${isUnsorted ? ' unsorted' : ''}`}
      style={accent ? ({ '--col-accent': accent } as React.CSSProperties) : undefined}
    >
      <header className="column-head">
        {renaming && edit ? (
          <input
            className="rename"
            autoFocus
            defaultValue={group.name}
            onBlur={(e) => {
              const v = e.currentTarget.value.trim();
              if (v && v !== group.name) edit.onRename(group.id, v);
              setRenaming(false);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') e.currentTarget.blur();
              if (e.key === 'Escape') setRenaming(false);
            }}
          />
        ) : (
          <h3
            onDoubleClick={() => group.editable && setRenaming(true)}
            title={group.editable ? 'Double-click to rename' : undefined}
          >
            {group.name}
          </h3>
        )}
        <span className="count">{countCards(group.cards)}</span>
        {edit && group.editable && !renaming && (
          <span className="col-actions">
            <button className="icon" title="Move left" disabled={isFirst} onClick={() => edit.onShift(group.id, -1)}>
              ‹
            </button>
            <button className="icon" title="Move right" disabled={isLast} onClick={() => edit.onShift(group.id, 1)}>
              ›
            </button>
            <button className="icon" title="Rename" onClick={() => setRenaming(true)}>
              ✎
            </button>
            <button
              className="icon danger"
              title="Delete group (its cards become Unsorted)"
              onClick={() => edit.onDelete(group.id)}
            >
              ×
            </button>
          </span>
        )}
      </header>
      <div className="column-body">
        {group.cards.map((c) => (
          <DraggableCard
            key={c.key}
            card={c}
            groupId={group.id}
            draggable={!!edit}
            selected={c.key === selectedKey}
            onSelect={onSelect}
          />
        ))}
        {group.cards.length === 0 && <div className="empty-col">{edit ? 'Drop cards here' : 'No cards'}</div>}
      </div>
    </section>
  );
}

function DraggableCard({
  card,
  groupId,
  draggable,
  selected,
  onSelect,
}: {
  card: Card;
  groupId: string;
  draggable: boolean;
  selected: boolean;
  onSelect: (card: Card) => void;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `${groupId}::${card.key}`,
    data: { card, groupId },
    disabled: !draggable,
  });
  return (
    <div
      ref={setNodeRef}
      {...(draggable ? listeners : {})}
      {...(draggable ? attributes : {})}
      className={`drag-wrap${isDragging ? ' dragging' : ''}${draggable ? ' can-drag' : ''}`}
    >
      <CardRow card={card} selected={selected} onSelect={onSelect} />
    </div>
  );
}

function AddColumn({ onAdd }: { onAdd: (name: string) => void }) {
  const [name, setName] = useState('');
  return (
    <form
      className="column add-column"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) onAdd(name.trim());
        setName('');
      }}
    >
      <input placeholder="New group name…" value={name} onChange={(e) => setName(e.target.value)} />
      <button type="submit" disabled={!name.trim()}>
        Add group
      </button>
    </form>
  );
}
