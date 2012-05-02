"""
Simulation builder.

@author: Gautham Ganapathy
@organization: Textensor (http://textensor.com)
@contact: gautham@textensor.com, gautham@lisphacker.org
"""

from pylems.base.base import PyLEMSBase
from pylems.base.errors import SimBuildError
from pylems.sim.runnable import Runnable
from pylems.sim.sim import Simulation
from pylems.parser.expr import ExprNode
from pylems.model.behavior import EventHandler,Action

class SimulationBuilder(PyLEMSBase):
    """
    Simulation builder class.
    """
    
    def __init__(self, model):
        """
        Constructor.

        @param model: Model upon which the simulation is to be generated.
        @type model: pylems.model.model.Model
        """
        
        self.model = model

    def build(self):
        """
        Build the simulation components from the model.
        """

        sim = Simulation()

        for component_name in self.model.default_runs:
            if component_name not in self.model.context.components:
                raise SimBuildError('Unable to find component \'{0}\' to run'\
                                    .format(component_name))
            component = self.model.context.components[component_name]

            runnable = self.build_runnable(component)
            sim.add_runnable(runnable)

    def build_runnable(self, component):
        runnable = Runnable()
        context = component.context

        print 'Building ' + component.id
        
        for pn in context.parameters:
            p = context.parameters[pn]
            if p.numeric_value:
                runnable.add_instance_variable(p.name, p.numeric_value)
                runnable.add_instance_variable(p.name + '_shadow',
                                               p.numeric_value)
            else:
                if p.dimension == '__component_ref__':
                    ref = context.parent.lookup_component(p.value)
                    if ref == None:
                        raise SimBuildError(('Unable to resolve component '
                                             'reference {0}').\
                                            format(component_name))
                    self.build_runnable(ref)

        if context.selected_behavior_profile:
            self.add_runnable_behavior(runnable,
                                       context.selected_behavior_profile)

    def add_runnable_behavior(self, runnable, behavior_profile):
        regime = behavior_profile.default_regime

        for svn in regime.state_variables:
            sv = regime.state_variables[svn]
            runnable.add_instance_variable(sv.name, 0)
            runnable.add_instance_variable(sv.name + '_shadow', 0)

        time_step_code = []
        for tdn in regime.time_derivatives:
            if tdn not in regime.state_variables:
                raise SimBuildError(('Time derivative for undefined state '
                                     'variable {0}').format(tdn))
            
            td = regime.time_derivatives[tdn]
            time_step_code += ['self.{0} += dt * ({1})'.format(td.variable,
                               self.build_expression_from_tree(\
                                   td.expression_tree))]
        runnable.add_method('update_state_variables', ['self', 'dt'],
                            time_step_code)

        event_handler_code = []
        for eh in regime.event_handlers:
            print self.build_event_handler(eh)
            event_handler_code += self.build_event_handler(eh)

        runnable.add_method('run_postprocessing_event_handlers', ['self'],
                            event_handler_code)

    def convert_op(self, op):
        if op == '.gt.':
            return '>'
        elif op == '.ge.':
            return '>='
        elif op == '.lt.':
            return '<'
        elif op == '.le.':
            return '<='
        elif op == '.eq.':
            return '=='
        elif op == '.ne.':
            return '!e'
        else:
            return op
        
    def build_expression_from_tree(self, tree_node):
        if tree_node.type == ExprNode.VALUE:
            if tree_node.value[0].isalpha():
                return 'self.{0}_shadow'.format(tree_node.value)
            else:
                return tree_node.value
        else:
            return '({0}) {1} ({2})'.format(\
                self.build_expression_from_tree(tree_node.left),
                self.convert_op(tree_node.op),
                self.build_expression_from_tree(tree_node.right))

    def build_event_handler(self, event_handler):
        if event_handler.type == EventHandler.ON_CONDITION:
            return self.build_on_condition(event_handler)
        else:
            return []

    def build_on_condition(self, on_condition):
        on_condition_code = []

        on_condition_code += ['if {0}:'.format(\
            self.build_expression_from_tree(on_condition.expression_tree))]

        for action in on_condition.actions:
            on_condition_code += ['    ' + self.build_action(action)]

        return on_condition_code
            
    def build_action(self, action):
        if action.type == Action.STATE_ASSIGNMENT:
            return self.build_state_assignment(action)
        else:
            return ''

    def build_state_assignment(self, state_assignment):
        return 'self.{0} = {1}'.format(\
            state_assignment.variable,
            self.build_expression_from_tree(state_assignment.expression_tree))
