/*
 * Copyright (c) 2019 SUSE LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

package skuba

import (
	"github.com/spf13/cobra"

	"github.com/SUSE/skuba/internal/app/skuba/node"
)

func NewNodeCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "node",
		Short: "Commands to handle a specific node",
	}

	cmd.AddCommand(
		node.NewBootstrapCmd(),
		node.NewJoinCmd(),
		node.NewRemoveCmd(),
		node.NewUpgradeCmd(),
	)

	return cmd
}
