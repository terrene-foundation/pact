// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Org Builder page -- visual D/T/R tree builder for organizational
 * governance structures.
 *
 * Provides a tree view of Departments, Teams, and Roles with forms
 * to add new units at each level. Supports YAML export for
 * configuration files.
 *
 * D/T/R grammar: every Department or Team MUST be immediately followed
 * by exactly one Role. This builder enforces that invariant.
 */

"use client";

import { useState, useCallback, useMemo } from "react";
import DashboardShell from "../../components/layout/DashboardShell";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { useAuth } from "../../lib/auth-context";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface OrgRole {
  id: string;
  name: string;
  clearance_level: string;
}

interface OrgTeam {
  id: string;
  name: string;
  role: OrgRole;
  roles: OrgRole[];
}

interface OrgDepartment {
  id: string;
  name: string;
  role: OrgRole;
  teams: OrgTeam[];
}

interface OrgTree {
  org_name: string;
  departments: OrgDepartment[];
}

type AddMode =
  | { type: "department" }
  | { type: "team"; departmentId: string }
  | { type: "role"; departmentId: string; teamId?: string }
  | null;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CLEARANCE_LEVELS = [
  { value: "PUBLIC", label: "Public" },
  { value: "RESTRICTED", label: "Restricted" },
  { value: "CONFIDENTIAL", label: "Confidential" },
  { value: "SECRET", label: "Secret" },
  { value: "TOP_SECRET", label: "Top Secret" },
] as const;

const CLEARANCE_COLORS: Record<string, string> = {
  PUBLIC: "bg-green-100 text-green-700 border-green-300",
  RESTRICTED: "bg-blue-100 text-blue-700 border-blue-300",
  CONFIDENTIAL: "bg-yellow-100 text-yellow-800 border-yellow-300",
  SECRET: "bg-orange-100 text-orange-800 border-orange-300",
  TOP_SECRET: "bg-red-100 text-red-800 border-red-300",
};

// ---------------------------------------------------------------------------
// ID generation
// ---------------------------------------------------------------------------

let nextId = 1;
function genId(prefix: string): string {
  return `${prefix}-${nextId++}`;
}

// ---------------------------------------------------------------------------
// YAML export
// ---------------------------------------------------------------------------

function indent(level: number): string {
  return "  ".repeat(level);
}

function toYaml(tree: OrgTree): string {
  const lines: string[] = [];
  lines.push(`org_name: "${tree.org_name}"`);
  lines.push("departments:");

  for (const dept of tree.departments) {
    lines.push(`${indent(1)}- name: "${dept.name}"`);
    lines.push(`${indent(2)}id: "${dept.id}"`);
    lines.push(`${indent(2)}role:`);
    lines.push(`${indent(3)}name: "${dept.role.name}"`);
    lines.push(`${indent(3)}clearance: ${dept.role.clearance_level}`);

    if (dept.teams.length > 0) {
      lines.push(`${indent(2)}teams:`);
      for (const team of dept.teams) {
        lines.push(`${indent(3)}- name: "${team.name}"`);
        lines.push(`${indent(4)}id: "${team.id}"`);
        lines.push(`${indent(4)}role:`);
        lines.push(`${indent(5)}name: "${team.role.name}"`);
        lines.push(`${indent(5)}clearance: ${team.role.clearance_level}`);

        if (team.roles.length > 0) {
          lines.push(`${indent(4)}additional_roles:`);
          for (const role of team.roles) {
            lines.push(`${indent(5)}- name: "${role.name}"`);
            lines.push(`${indent(6)}clearance: ${role.clearance_level}`);
          }
        }
      }
    }
  }

  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ClearanceBadge({ level }: { level: string }) {
  const colorClass =
    CLEARANCE_COLORS[level] ?? "bg-gray-100 text-gray-700 border-gray-300";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${colorClass}`}
    >
      {level}
    </span>
  );
}

function TreeNode({
  label,
  kind,
  depth,
  children,
  actions,
}: {
  label: string;
  kind: "department" | "team" | "role";
  depth: number;
  children?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  const kindColors: Record<string, string> = {
    department: "border-l-blue-500 bg-blue-50",
    team: "border-l-indigo-500 bg-indigo-50",
    role: "border-l-green-500 bg-green-50",
  };
  const kindLabels: Record<string, string> = {
    department: "D",
    team: "T",
    role: "R",
  };
  const kindBadgeColors: Record<string, string> = {
    department: "bg-blue-200 text-blue-800",
    team: "bg-indigo-200 text-indigo-800",
    role: "bg-green-200 text-green-800",
  };

  return (
    <div style={{ marginLeft: `${depth * 24}px` }} className="mt-2">
      <div
        className={`flex items-center justify-between rounded-md border-l-4 px-3 py-2 ${kindColors[kind] ?? "border-l-gray-300 bg-gray-50"}`}
      >
        <div className="flex items-center gap-2">
          <span
            className={`flex h-5 w-5 items-center justify-center rounded text-xs font-bold ${kindBadgeColors[kind] ?? "bg-gray-200 text-gray-700"}`}
          >
            {kindLabels[kind] ?? "?"}
          </span>
          <span className="text-sm font-medium text-gray-900">{label}</span>
        </div>
        {actions && <div className="flex items-center gap-1">{actions}</div>}
      </div>
      {children}
    </div>
  );
}

function AddForm({
  mode,
  onSubmit,
  onCancel,
}: {
  mode: NonNullable<AddMode>;
  onSubmit: (data: { name: string; clearance_level: string }) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [clearance, setClearance] = useState("RESTRICTED");

  const typeLabel =
    mode.type === "department"
      ? "Department"
      : mode.type === "team"
        ? "Team"
        : "Role";

  const needsRole = mode.type === "department" || mode.type === "team";
  const formTitle = needsRole
    ? `Add ${typeLabel} (with required Role)`
    : "Add Additional Role";

  return (
    <div className="mt-2 rounded-md border border-gray-300 bg-white p-4 shadow-sm">
      <h4 className="mb-3 text-sm font-semibold text-gray-800">{formTitle}</h4>
      <div className="space-y-3">
        <div>
          <label
            htmlFor="add-name"
            className="block text-xs font-medium text-gray-600"
          >
            {typeLabel} Name
          </label>
          <input
            id="add-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder={`e.g. ${mode.type === "department" ? "Engineering" : mode.type === "team" ? "Backend" : "Developer"}`}
            autoFocus
          />
        </div>
        <div>
          <label
            htmlFor="add-clearance"
            className="block text-xs font-medium text-gray-600"
          >
            {needsRole ? "Role " : ""}Clearance Level
          </label>
          <select
            id="add-clearance"
            value={clearance}
            onChange={(e) => setClearance(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {CLEARANCE_LEVELS.map((cl) => (
              <option key={cl.value} value={cl.value}>
                {cl.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              if (name.trim()) {
                onSubmit({ name: name.trim(), clearance_level: clearance });
              }
            }}
            disabled={!name.trim()}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            Add {typeLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function OrgBuilderPage() {
  const { user } = useAuth();

  const [tree, setTree] = useState<OrgTree>({
    org_name: "My Organization",
    departments: [],
  });

  const [addMode, setAddMode] = useState<AddMode>(null);
  const [exportVisible, setExportVisible] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);

  // Add department
  const addDepartment = useCallback(
    (data: { name: string; clearance_level: string }) => {
      const deptId = genId("dept");
      const newDept: OrgDepartment = {
        id: deptId,
        name: data.name,
        role: {
          id: genId("role"),
          name: `${data.name} Lead`,
          clearance_level: data.clearance_level,
        },
        teams: [],
      };
      setTree((t) => ({
        ...t,
        departments: [...t.departments, newDept],
      }));
      setAddMode(null);
    },
    [],
  );

  // Add team to department
  const addTeam = useCallback(
    (departmentId: string, data: { name: string; clearance_level: string }) => {
      const teamId = genId("team");
      const newTeam: OrgTeam = {
        id: teamId,
        name: data.name,
        role: {
          id: genId("role"),
          name: `${data.name} Lead`,
          clearance_level: data.clearance_level,
        },
        roles: [],
      };
      setTree((t) => ({
        ...t,
        departments: t.departments.map((d) =>
          d.id === departmentId ? { ...d, teams: [...d.teams, newTeam] } : d,
        ),
      }));
      setAddMode(null);
    },
    [],
  );

  // Add additional role to team
  const addRole = useCallback(
    (
      departmentId: string,
      teamId: string | undefined,
      data: { name: string; clearance_level: string },
    ) => {
      const newRole: OrgRole = {
        id: genId("role"),
        name: data.name,
        clearance_level: data.clearance_level,
      };

      if (teamId) {
        setTree((t) => ({
          ...t,
          departments: t.departments.map((d) =>
            d.id === departmentId
              ? {
                  ...d,
                  teams: d.teams.map((tm) =>
                    tm.id === teamId
                      ? { ...tm, roles: [...tm.roles, newRole] }
                      : tm,
                  ),
                }
              : d,
          ),
        }));
      }
      setAddMode(null);
    },
    [],
  );

  // Remove department
  const removeDepartment = useCallback((deptId: string) => {
    setTree((t) => ({
      ...t,
      departments: t.departments.filter((d) => d.id !== deptId),
    }));
  }, []);

  // Remove team
  const removeTeam = useCallback((deptId: string, teamId: string) => {
    setTree((t) => ({
      ...t,
      departments: t.departments.map((d) =>
        d.id === deptId
          ? { ...d, teams: d.teams.filter((tm) => tm.id !== teamId) }
          : d,
      ),
    }));
  }, []);

  // Remove additional role
  const removeRole = useCallback(
    (deptId: string, teamId: string, roleId: string) => {
      setTree((t) => ({
        ...t,
        departments: t.departments.map((d) =>
          d.id === deptId
            ? {
                ...d,
                teams: d.teams.map((tm) =>
                  tm.id === teamId
                    ? {
                        ...tm,
                        roles: tm.roles.filter((r) => r.id !== roleId),
                      }
                    : tm,
                ),
              }
            : d,
        ),
      }));
    },
    [],
  );

  // Handle add form submission based on mode
  const handleAddSubmit = useCallback(
    (data: { name: string; clearance_level: string }) => {
      if (!addMode) return;
      if (addMode.type === "department") {
        addDepartment(data);
      } else if (addMode.type === "team") {
        addTeam(addMode.departmentId, data);
      } else if (addMode.type === "role") {
        addRole(addMode.departmentId, addMode.teamId, data);
      }
    },
    [addMode, addDepartment, addTeam, addRole],
  );

  // YAML export
  const yamlContent = useMemo(() => toYaml(tree), [tree]);

  const handleCopyYaml = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(yamlContent);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = yamlContent;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    }
  }, [yamlContent]);

  // Node counts for summary
  const totalDepts = tree.departments.length;
  const totalTeams = tree.departments.reduce(
    (sum, d) => sum + d.teams.length,
    0,
  );
  const totalRoles = tree.departments.reduce(
    (sum, d) =>
      sum +
      1 + // department role
      d.teams.reduce(
        (tSum, t) => tSum + 1 + t.roles.length, // team role + additional roles
        0,
      ),
    0,
  );

  const removeBtn = (onClick: () => void) => (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className="rounded px-1.5 py-0.5 text-xs text-red-600 hover:bg-red-100 transition-colors"
      title="Remove"
    >
      Remove
    </button>
  );

  return (
    <DashboardShell
      activePath="/org-builder"
      title="Org Builder"
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Org Builder" },
      ]}
      actions={
        <div className="flex gap-2">
          <button
            onClick={() => setExportVisible((v) => !v)}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            {exportVisible ? "Hide YAML" : "Export YAML"}
          </button>
        </div>
      }
    >
      <div className="space-y-6">
        <p className="text-sm text-gray-600">
          Build organizational governance structures using the D/T/R grammar.
          Every Department (D) and Team (T) must have exactly one required Role
          (R). Additional roles can be added within teams.
        </p>

        {/* Org name */}
        <div className="flex items-center gap-3">
          <label
            htmlFor="org-name"
            className="text-sm font-medium text-gray-700"
          >
            Organization:
          </label>
          <input
            id="org-name"
            type="text"
            value={tree.org_name}
            onChange={(e) =>
              setTree((t) => ({ ...t, org_name: e.target.value }))
            }
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Summary */}
        {totalDepts > 0 && (
          <div className="flex flex-wrap items-center gap-4 rounded-lg border border-gray-200 bg-white px-4 py-3">
            <div className="flex items-center gap-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded bg-blue-200 text-xs font-bold text-blue-800">
                D
              </span>
              <span className="text-sm text-gray-600">
                {totalDepts} department{totalDepts !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded bg-indigo-200 text-xs font-bold text-indigo-800">
                T
              </span>
              <span className="text-sm text-gray-600">
                {totalTeams} team{totalTeams !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded bg-green-200 text-xs font-bold text-green-800">
                R
              </span>
              <span className="text-sm text-gray-600">
                {totalRoles} role{totalRoles !== 1 ? "s" : ""}
              </span>
            </div>
          </div>
        )}

        {/* YAML export panel */}
        {exportVisible && (
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-700">
                YAML Export
              </h3>
              <button
                onClick={handleCopyYaml}
                className="rounded-md border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                {copySuccess ? "Copied" : "Copy to Clipboard"}
              </button>
            </div>
            <pre className="max-h-80 overflow-auto rounded-md bg-gray-900 p-4 text-xs text-green-400 font-mono">
              {yamlContent}
            </pre>
          </div>
        )}

        {/* Tree */}
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-800">
              Organization Structure
            </h3>
            <button
              onClick={() => setAddMode({ type: "department" })}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 transition-colors"
            >
              + Department
            </button>
          </div>

          {tree.departments.length === 0 && !addMode && (
            <div className="rounded-md border border-dashed border-gray-300 p-8 text-center">
              <p className="text-sm text-gray-500">
                Start building your organization by adding a department.
              </p>
            </div>
          )}

          {/* Department tree */}
          {tree.departments.map((dept) => (
            <div key={dept.id}>
              {/* Department node */}
              <TreeNode
                label={dept.name}
                kind="department"
                depth={0}
                actions={removeBtn(() => removeDepartment(dept.id))}
              >
                {/* Department required role */}
                <TreeNode
                  label={dept.role.name}
                  kind="role"
                  depth={1}
                  actions={<ClearanceBadge level={dept.role.clearance_level} />}
                />

                {/* Teams */}
                {dept.teams.map((team) => (
                  <div key={team.id}>
                    <TreeNode
                      label={team.name}
                      kind="team"
                      depth={1}
                      actions={
                        <div className="flex items-center gap-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setAddMode({
                                type: "role",
                                departmentId: dept.id,
                                teamId: team.id,
                              });
                            }}
                            className="rounded px-1.5 py-0.5 text-xs text-blue-600 hover:bg-blue-100 transition-colors"
                          >
                            + Role
                          </button>
                          {removeBtn(() => removeTeam(dept.id, team.id))}
                        </div>
                      }
                    >
                      {/* Team required role */}
                      <TreeNode
                        label={team.role.name}
                        kind="role"
                        depth={2}
                        actions={
                          <ClearanceBadge level={team.role.clearance_level} />
                        }
                      />

                      {/* Additional roles */}
                      {team.roles.map((role) => (
                        <TreeNode
                          key={role.id}
                          label={role.name}
                          kind="role"
                          depth={2}
                          actions={
                            <div className="flex items-center gap-1">
                              <ClearanceBadge level={role.clearance_level} />
                              {removeBtn(() =>
                                removeRole(dept.id, team.id, role.id),
                              )}
                            </div>
                          }
                        />
                      ))}

                      {/* Add role form (inline under team) */}
                      {addMode?.type === "role" &&
                        "teamId" in addMode &&
                        addMode.teamId === team.id && (
                          <div style={{ marginLeft: "48px" }}>
                            <AddForm
                              mode={addMode}
                              onSubmit={handleAddSubmit}
                              onCancel={() => setAddMode(null)}
                            />
                          </div>
                        )}
                    </TreeNode>
                  </div>
                ))}

                {/* Add team button */}
                <div style={{ marginLeft: "24px" }} className="mt-2">
                  <button
                    onClick={() =>
                      setAddMode({ type: "team", departmentId: dept.id })
                    }
                    className="rounded-md border border-dashed border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-500 hover:border-indigo-400 hover:text-indigo-600 transition-colors"
                  >
                    + Add Team to {dept.name}
                  </button>
                </div>

                {/* Add team form (inline under department) */}
                {addMode?.type === "team" &&
                  addMode.departmentId === dept.id && (
                    <div style={{ marginLeft: "24px" }}>
                      <AddForm
                        mode={addMode}
                        onSubmit={handleAddSubmit}
                        onCancel={() => setAddMode(null)}
                      />
                    </div>
                  )}
              </TreeNode>
            </div>
          ))}

          {/* Add department form */}
          {addMode?.type === "department" && (
            <AddForm
              mode={addMode}
              onSubmit={handleAddSubmit}
              onCancel={() => setAddMode(null)}
            />
          )}
        </div>
      </div>
    </DashboardShell>
  );
}
