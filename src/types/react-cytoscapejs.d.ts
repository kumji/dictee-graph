declare module 'react-cytoscapejs' {
  import type { Core, ElementDefinition, Stylesheet, LayoutOptions } from 'cytoscape'
  import type { CSSProperties, Component } from 'react'

  export interface CytoscapeComponentProps {
    elements: ElementDefinition[]
    style?: CSSProperties
    stylesheet?: Stylesheet[]
    layout?: LayoutOptions
    cy?: (cy: Core) => void
    className?: string
  }

  export default class CytoscapeComponent extends Component<CytoscapeComponentProps> {}
}

declare module 'cytoscape-cose-bilkent' {
  import type { Ext } from 'cytoscape'
  const register: Ext
  export default register
}
