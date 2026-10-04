import type { Core, NodeSingular } from 'cytoscape'
import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force'
import { nodeSize } from './graphStyles'

// 레이아웃 튜닝 값 — 연구자 피드백("조금 더 넓게/강하게")은 여기 숫자만 조정하면 된다.
export const FORCE_PARAMS = {
  linkDistance: 80, // 두 노드 가장자리 사이 목표 거리 (반지름은 별도로 더해짐)
  chargeStrength: -420, // 노드 간 반발력 (음수일수록 강함)
  chargeDistanceMax: 600,
  collidePadding: 10, // 충돌 반경 여유값
  labelHalfWidthMax: 70, // 충돌 반경에 반영할 라벨 반폭 상한 (긴 라벨이 과도하게 밀어내지 않도록)
  centerStrength: 0.05, // 연결 없는 노드가 멀리 날아가지 않도록 잡아주는 힘
  hoverLensBoost: 45, // 호버 시 충돌 반경 추가량 → 주변 노드가 비켜나는 정도
  neighborLensBoost: 12, // 호버 시 이웃 노드(함께 확대됨)의 충돌 반경 추가량
  initialTicks: 300,
}

const LABEL_FONT_SIZE = 10

interface SimNode extends SimulationNodeDatum {
  id: string
  radius: number
  labelHalfWidth: number
  lensBoost: number
}

type SimLink = SimulationLinkDatum<SimNode>

function estimateLabelWidth(label: string) {
  let w = 0
  for (const ch of label) w += ch.charCodeAt(0) > 0x1100 ? LABEL_FONT_SIZE : LABEL_FONT_SIZE * 0.58
  return w
}

function collideRadius(n: SimNode) {
  const labelHalf = Math.min(n.labelHalfWidth, FORCE_PARAMS.labelHalfWidthMax)
  return Math.max(n.radius, labelHalf) + FORCE_PARAMS.collidePadding + n.lensBoost
}

export interface ForceLayout {
  /** 라벨이 바뀌었을 때(언어 토글) 충돌 반경 재계산 */
  refreshLabels: () => void
  destroy: () => void
}

export function startForceLayout(cy: Core): ForceLayout {
  const nodes: SimNode[] = cy.nodes().map((n) => ({
    id: n.id(),
    radius: nodeSize(n) / 2,
    labelHalfWidth: estimateLabelWidth(String(n.data('label') ?? '')) / 2,
    lensBoost: 0,
  }))
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const links: SimLink[] = cy.edges().map((e) => ({ source: e.source().id(), target: e.target().id() }))

  const collide = forceCollide<SimNode>(collideRadius).strength(0.9).iterations(2)

  const sim: Simulation<SimNode, SimLink> = forceSimulation(nodes)
    .force(
      'link',
      forceLink<SimNode, SimLink>(links)
        .id((d) => d.id)
        .distance((l) => {
          const s = l.source as SimNode
          const t = l.target as SimNode
          return s.radius + t.radius + FORCE_PARAMS.linkDistance
        }),
    )
    .force('charge', forceManyBody<SimNode>().strength(FORCE_PARAMS.chargeStrength).distanceMax(FORCE_PARAMS.chargeDistanceMax))
    .force('collide', collide)
    .force('x', forceX<SimNode>(0).strength(FORCE_PARAMS.centerStrength))
    .force('y', forceY<SimNode>(0).strength(FORCE_PARAMS.centerStrength))
    .stop()

  // 첫 화면은 이미 자리 잡힌 상태로 보여준다
  sim.tick(FORCE_PARAMS.initialTicks)

  const grabbed = new Set<string>()
  const syncPositions = () => {
    cy.batch(() => {
      nodes.forEach((n) => {
        if (grabbed.has(n.id)) return
        cy.getElementById(n.id).position({ x: n.x ?? 0, y: n.y ?? 0 })
      })
    })
  }
  syncPositions()
  cy.fit(undefined, 40)

  sim.on('tick', syncPositions)

  // --- 드래그: 잡은 노드를 고정점으로 두고 시뮬레이션을 깨워 주변이 따라오게 ---
  const onGrab = (evt: cytoscape.EventObject) => {
    const n = byId.get(evt.target.id())
    if (!n) return
    grabbed.add(n.id)
    const p = (evt.target as NodeSingular).position()
    n.fx = p.x
    n.fy = p.y
    sim.alphaTarget(0.3).restart()
  }
  const onDrag = (evt: cytoscape.EventObject) => {
    const n = byId.get(evt.target.id())
    if (!n) return
    const p = (evt.target as NodeSingular).position()
    n.fx = p.x
    n.fy = p.y
  }
  const onFree = (evt: cytoscape.EventObject) => {
    const n = byId.get(evt.target.id())
    if (!n) return
    grabbed.delete(n.id)
    n.fx = null
    n.fy = null
    sim.alphaTarget(0)
  }

  // --- 호버 렌즈: 이웃 강조 + 충돌 반경 확대로 주변 노드가 부드럽게 비켜남 ---
  const clearFocus = () => {
    cy.elements().removeClass('hovered neighbor faded')
  }
  const focus = (node: NodeSingular) => {
    clearFocus()
    const hood = node.closedNeighborhood()
    cy.elements().not(hood).addClass('faded')
    hood.addClass('neighbor')
    node.removeClass('neighbor').addClass('hovered')
  }

  const onOver = (evt: cytoscape.EventObject) => {
    const node = evt.target as NodeSingular
    focus(node)
    const n = byId.get(node.id())
    if (!n || grabbed.size > 0) return
    // 커서 아래 노드는 고정해서 도망가지 않게
    n.fx = n.x
    n.fy = n.y
    n.lensBoost = FORCE_PARAMS.hoverLensBoost
    node.neighborhood('node').forEach((nb) => {
      const sn = byId.get(nb.id())
      if (sn) sn.lensBoost = FORCE_PARAMS.neighborLensBoost
    })
    collide.radius(collideRadius)
    sim.alpha(Math.max(sim.alpha(), 0.25)).restart()
  }
  const onOut = (evt: cytoscape.EventObject) => {
    clearFocus()
    const n = byId.get(evt.target.id())
    if (!n || grabbed.has(n.id)) return
    n.fx = null
    n.fy = null
    if (n.lensBoost === 0) return
    nodes.forEach((sn) => (sn.lensBoost = 0))
    collide.radius(collideRadius)
    sim.alpha(Math.max(sim.alpha(), 0.15)).restart()
  }

  // 터치 기기(호버 없음): 탭으로 이웃 강조, 빈 곳 탭으로 해제
  const onTapNode = (evt: cytoscape.EventObject) => focus(evt.target as NodeSingular)
  const onTapBg = (evt: cytoscape.EventObject) => {
    if (evt.target === cy) clearFocus()
  }

  cy.on('grab', 'node', onGrab)
  cy.on('drag', 'node', onDrag)
  cy.on('free', 'node', onFree)
  cy.on('mouseover', 'node', onOver)
  cy.on('mouseout', 'node', onOut)
  cy.on('tap', 'node', onTapNode)
  cy.on('tap', onTapBg)

  return {
    refreshLabels() {
      cy.nodes().forEach((cn) => {
        const n = byId.get(cn.id())
        if (n) n.labelHalfWidth = estimateLabelWidth(String(cn.data('label') ?? '')) / 2
      })
      collide.radius(collideRadius)
      sim.alpha(0.3).restart()
    },
    destroy() {
      sim.stop()
      sim.on('tick', null)
      cy.removeListener('grab', 'node', onGrab)
      cy.removeListener('drag', 'node', onDrag)
      cy.removeListener('free', 'node', onFree)
      cy.removeListener('mouseover', 'node', onOver)
      cy.removeListener('mouseout', 'node', onOut)
      cy.removeListener('tap', 'node', onTapNode)
      cy.removeListener('tap', onTapBg)
    },
  }
}
