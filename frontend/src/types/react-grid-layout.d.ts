declare module "react-grid-layout" {
  import * as React from "react";

  export interface Layout {
    i: string;
    x: number;
    y: number;
    w: number;
    h: number;
    minW?: number;
    maxW?: number;
    minH?: number;
    maxH?: number;
    static?: boolean;
    isDraggable?: boolean;
    isResizable?: boolean;
  }

  export interface Layouts {
    [breakpoint: string]: Layout[];
  }

  export interface ResponsiveProps {
    className?: string;
    layouts?: Layouts;
    breakpoints?: { [breakpoint: string]: number };
    cols?: { [breakpoint: string]: number };
    rowHeight?: number;
    width?: number;
    isDraggable?: boolean;
    isResizable?: boolean;
    margin?: [number, number];
    containerPadding?: [number, number];
    draggableHandle?: string;
    resizeHandles?: Array<"s" | "w" | "e" | "n" | "sw" | "nw" | "se" | "ne">;
    onLayoutChange?: (layout: Layout[], layouts: Layouts) => void;
    children?: React.ReactNode;
    style?: React.CSSProperties;
  }

  export interface WidthProviderProps {
    measureBeforeMount?: boolean;
  }

  export class Responsive extends React.Component<ResponsiveProps> {}
  export function WidthProvider<P>(
    component: React.ComponentType<P>
  ): React.ComponentType<P & WidthProviderProps>;
}
