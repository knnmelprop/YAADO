# FlightDeck

**FlightDeck** is the central orchestrator and "brain" of the YAADO framework. It takes the parsed vehicle geometry from `ComponentStore` and the physical calculations from `modules/`, and runs them through mission simulations and optimization loops.

## Architectural Vision: The "Hidden OpenMDAO" Engine

The overarching philosophy of `FlightDeck` is to provide **world-class Multidisciplinary Design Optimization (MDO) without the steep learning curve.**

As of now, in the aerospace industry **OpenMDAO** is the undisputed industry standard for massive-scale optimization because of its use of analytic derivatives. However, it is notoriously complex and difficult for students to learn.

### Abstraction

My ([Arseni's](https://github.com/Arseni10Lk)) vision for `FlightDeck` is to use OpenMDAO as the underlying computational engine, but keep it **completely hidden from the end-user**. 

A person using YAADO should never have to manually define an OpenMDAO `Problem()`, manage `ExplicitComponent` blocks, or manually wire variables together using `connect()`. 

For example:
1. The user provides a declarative TOML configuration.
2. `FlightDeck` dynamically reads the `BaseVehicleConfig` and automatically translates it into an OpenMDAO tree in the background.
3. OpenMDAO optimizes the vehicle (adjusting wing spans, engine thrusts, and masses).
4. The optimized parameters are returned to the user.

In short: **OpenMDAO provides the horsepower, but YAADO provides the steering wheel.**
