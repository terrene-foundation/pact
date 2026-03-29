// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Barrel export for all Shadcn UI components.
 *
 * Import from "@/components/ui/shadcn" for clean access:
 *   import { Button, Card, CardHeader } from "@/components/ui/shadcn";
 */

// --- Alert ---
export { Alert, AlertTitle, AlertDescription } from "./alert";

// --- Alert Dialog ---
export {
  AlertDialog,
  AlertDialogPortal,
  AlertDialogOverlay,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
} from "./alert-dialog";

// --- Avatar ---
export { Avatar, AvatarImage, AvatarFallback } from "./avatar";

// --- Badge ---
export { Badge, badgeVariants } from "./badge";
export type { BadgeProps } from "./badge";

// --- Button ---
export { Button, buttonVariants } from "./button";
export type { ButtonProps } from "./button";

// --- Card ---
export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardContent,
} from "./card";

// --- Checkbox ---
export { Checkbox } from "./checkbox";

// --- Dialog ---
export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogClose,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "./dialog";

// --- Dropdown Menu ---
export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuGroup,
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuRadioGroup,
} from "./dropdown-menu";

// --- Form ---
export {
  useFormField,
  Form,
  FormItem,
  FormLabel,
  FormControl,
  FormDescription,
  FormMessage,
  FormField,
} from "./form";

// --- Input ---
export { Input } from "./input";

// --- Label ---
export { Label } from "./label";

// --- Popover ---
export { Popover, PopoverTrigger, PopoverContent } from "./popover";

// --- Progress ---
export { Progress } from "./progress";

// --- Scroll Area ---
export { ScrollArea, ScrollBar } from "./scroll-area";

// --- Select ---
export {
  Select,
  SelectGroup,
  SelectValue,
  SelectTrigger,
  SelectContent,
  SelectLabel,
  SelectItem,
  SelectSeparator,
} from "./select";

// --- Separator ---
export { Separator } from "./separator";

// --- Sheet ---
export {
  Sheet,
  SheetPortal,
  SheetOverlay,
  SheetTrigger,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetFooter,
  SheetTitle,
  SheetDescription,
} from "./sheet";

// --- Skeleton ---
export { Skeleton } from "./skeleton";

// --- Switch ---
export { Switch } from "./switch";

// --- Table ---
export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
} from "./table";

// --- Tabs ---
export { Tabs, TabsList, TabsTrigger, TabsContent } from "./tabs";

// --- Textarea ---
export { Textarea } from "./textarea";

// --- Toast ---
export {
  ToastProvider,
  ToastViewport,
  Toast,
  ToastTitle,
  ToastDescription,
  ToastClose,
  ToastAction,
} from "./toast";
export type { ToastActionElement, ToastProps } from "./toast";

// --- Toaster ---
export { Toaster } from "./toaster";

// --- Tooltip ---
export {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from "./tooltip";
