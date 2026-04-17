import Icon from './Icon.jsx'

export default function PanelToggle({ collapsed, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={collapsed ? 'Mostrar panel' : 'Ocultar panel'}
      className="absolute top-1/2 right-0 translate-x-1/2 -translate-y-1/2 w-[22px] h-11 rounded-md bg-bg-2 border border-border-strong text-fg-3 hover:bg-bg-3 hover:text-fg-1 hover:border-[var(--accent)] transition z-20 flex items-center justify-center"
    >
      <Icon
        name="chevron"
        size={12}
        strokeWidth={2}
        className={'transition-transform duration-300 ' + (collapsed ? 'rotate-180' : '')}
      />
    </button>
  )
}
